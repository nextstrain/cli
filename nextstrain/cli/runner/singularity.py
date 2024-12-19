"""
Run commands inside a container image using Singularity.

Singularity is a container system freely-available for Linux platforms.  It is
commonly available on institutional HPC systems as an alternative to Docker,
which is often not supported on such systems.  When you use Singularity with
the Nextstrain CLI, you don't need to install any other Nextstrain software
dependencies as validated versions are already bundled into a container image
by the Nextstrain team.

The Singularity runtime uses the same images built for the Docker runtime by
automatically converting them to local Singularity images.  Local images are
stored as files named
:file:`~/.nextstrain/runtimes/singularity/images/{repository}/{tag}.sif`.

.. versionadded:: 6.1.0


.. _singularity-setup:

Setup
=====

Run ``nextstrain setup singularity`` to get started.
Singularity version 3.0.0 or newer is required, but we recommend at least
version 3.10.0 or newer when possible.

This will download image layers totaling about 750 MB in size which are
converted to a final on-disk image of about 650 MB.  Transient disk usage
during this process peaks at about 2 GB.  These numbers are current as of
August 2023, as observed on Linux.  Numbers will vary over time, with a
tendency to slowly increase, and vary slightly by OS.

Note that the Singularity project forked into two separate projects in late
2021: `SingularityCE`_ under `Sylabs`_ and `Apptainer`_ under the `Linux
Foundation`_.  Either fork should work with Nextstrain CLI, as both projects
still provide very similar interfaces and functionality via the ``singularity``
command.  You can read `Sylab's announcement`_ and `Apptainer's announcement`_
for more information on the fork.

.. _SingularityCE: https://sylabs.io/singularity/
.. _Sylabs: https://sylabs.io/
.. _Apptainer: https://apptainer.org
.. _Linux Foundation: https://www.linuxfoundation.org/
.. _Sylab's announcement: https://sylabs.io/2022/06/singularityce-is-singularity/
.. _Apptainer's announcement: https://apptainer.org/news/community-announcement-20211130


.. _singularity-config:

Config file variables
=====================

Defaults for the corresponding command line options, specified in the
:doc:`config file </config/file>`.

.. glossary::

    :index:`singularity.image <configuration variable; singularity.image>`
        Default for ``--image`` when using the Singularity runtime, e.g.
        ``docker://nextstrain/base:build-20230525T143814Z``.

        Typically set initially by ``nextstrain setup`` and subsequently by
        ``nextstrain update``.


.. _singularity-env:

Environment variables
=====================

.. warning::
    For development only.  You don't need to set these during normal operation.

Defaults for the corresponding command line options, potentially overriding
defaults set by `config file variables`_.

.. envvar:: NEXTSTRAIN_SINGULARITY_IMAGE

    Default for ``--image`` when using the Singularity runtime.
"""

import itertools
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from packaging.version import Version, InvalidVersion
from pathlib import Path
from typing import Iterable, List, Optional, cast
from urllib.parse import urlsplit
from .. import config
from ..errors import UserError
from ..paths import RUNTIMES
from ..types import Env, RunnerModule, SetupStatus, SetupTestResults, UpdateStatus
from ..util import capture_output, colored, exec_or_return, runner_name, split_image_name, warn
from . import docker

flatten = itertools.chain.from_iterable


RUNTIME_ROOT = RUNTIMES / "singularity/"

IMAGES = RUNTIME_ROOT / "images/"

CACHE = RUNTIME_ROOT / "cache/"


# The default intentionally omits an explicit "latest" tag so that on the first
# `nextstrain update` it gets pinned in the config file to the most recent
# "build-*" tag.  Users can set an explicit "latest" tag in config to always
# use the most recent image and not pin to "build-*" tags.
#   (copied from ./docker.py on 5 Jan 2022)
DEFAULT_IMAGE = os.environ.get("NEXTSTRAIN_SINGULARITY_IMAGE") \
             or config.get("singularity", "image") \
             or "docker://nextstrain/base"


SINGULARITY_MINIMUM_VERSION = "3.0.0"

APPTAINER_MINIMUM_VERSION = "1.0.0" # forked from Singularity 3.9.5

SINGULARITY_CONFIG_ENV = {
    # Store image caches in our runtime root instead of ~/.singularity/…
    "SINGULARITY_CACHEDIR": str(CACHE),

    # PROMPT_COMMAND is used by Singularity 3.5.3 onwards to forcibly set PS1
    # to "Singularity> " on the first evaluation.¹  This happens *after* our
    # bashrc is evaluated, so our Nextstrain prompt is overwritten.
    # Singularity appends to any existing PROMPT_COMMAND value, so use a
    # well-placed comment char (#) to avoid evaluating what it appends.
    # Additionally unset PROMPT_COMMAND the first time it's evaluated so this
    # silly workaround doesn't happen on every prompt.
    #
    # We set this via the special-cased environment passthru instead of setting
    # it via an --env arg because --env is only first available in 3.6.0.
    #
    # ¹ <https://github.com/sylabs/singularity/commit/30823afc>
    #   <https://github.com/apptainer/singularity/pull/4616>
    #   <https://github.com/apptainer/singularity/issues/2721>
    "SINGULARITYENV_PROMPT_COMMAND": "unset PROMPT_COMMAND; #",
}

SINGULARITY_EXEC_ARGS = lambda: [
    # Increase isolation.
    #
    # In the future, we may find we want to use additional related flags to
    # further increase isolation.¹  Note, however, that we'll want to think
    # about the minimum Singularity version we want to support, as many flags
    # in this area are not available on older versions.
    #
    #   --compat                (available since 3.9.0; a bundle option)
    #     --containall            (available since 2.2; a bundle option)
    #       --contain
    #       --cleanenv
    #       --ipc
    #       --pid
    #     --writable-tmpfs        (3.0.0)
    #     --no-init               (3.0.0)
    #     --no-umask              (3.7.0)
    #     --no-eval               (3.10.0, Apptainer 1.1.0)
    #
    # We opt not to use the --compat bundle option itself mainly for broader
    # version compatibility but also because what it includes will likely
    # change over time with newer Singularity releases.  We'd rather a stable,
    # predictable set of behaviour of our choosing that maximizes
    # compatibility.
    #
    # The options we use here are compatible with Singularity 2.6.0 and newer.
    #
    # XXX TODO: Once Singularity 4.0 is released and widely available, we *may*
    # consider switching from --compat to --oci² for a) stronger Docker-like
    # isolation and b) no longer having to convert our Docker (OCI) images to
    # Singularity (SIF) images.  Alternatively, we may want to keep this
    # runtime as a "middle ground" between the relatively strict isolation of
    # our Docker runtime and the much looser isolation of the Conda runtime.
    # Not sure!
    #   -trs, 23 May 2023
    #
    # ¹ <https://docs.sylabs.io/guides/latest/user-guide/singularity_and_docker.html#docker-like-compat-flag>
    # ² <https://docs.sylabs.io/guides/latest/user-guide/oci_runtime.html#oci-mode>
    "--contain",

    # Don't mount anything at all at the container's value of HOME.  This is
    # necesary because --compat includes --containall which includes --contain
    # which makes HOME in the container an empty temporary directory.
    # --no-home is available since 2.6.0.
    "--no-home",

    # Singularity really wants to default HOME inside the container to the
    # value from outside the container, thus ignoring the value set by the
    # upstream Docker image which is only used as a default by the Singularity
    # image.  Singularity forbids using --env to directly override HOME, so
    # instead we use --home <src>:<dst> with two empty values.  <src> doesn't
    # apply because we use --no-home, and setting <dst> to an empty value
    # allows the container's default to apply (thus avoiding hardcoding it
    # here).
    "--home", ":",

    # Allow writes to the image filesystem, discarded at container exit, à la
    # Docker.  Snakemake, for example, needs to be able to write to HOME
    # (/nextstrain).
    "--writable-tmpfs",

    # Don't copy entire host environment.  We forward our own hostenv.
    "--cleanenv",

    # Don't evaluate the entrypoint command line (e.g. arguments passed via
    # `nextstrain build`) before exec-ing the entrypoint.  It leads to unwanted
    # substitutions that happen too early.
    *(["--no-eval"] if singularity_version_at_least("3.10.0", apptainer="1.1.0") else []),

    # Since we use --no-home above, avoid warnings about not being able to cd
    # to $HOME (the default behaviour).  run() will override this by specifying
    # --pwd again.
    "--pwd", "/",
]


def register_arguments(parser) -> None:
    """
    No-op.  No arguments necessary.
    """
    pass


def run(opts, argv, working_volume = None, extra_env: Env = {}, cpus: int = None, memory: int = None) -> int:
    docker.assert_volumes_exist(opts.volumes)

    # We require docker:// qualified image names in this runtime internally,
    # but the external --image option is common to a few runtimes and takes
    # unqualified names.
    #
    # XXX TODO: We could probably support other schemes Singularity supports…
    # but it's likely not worth it until we have a need (if ever).
    #   -trs, 5 Jan 2023
    image = f"docker://{opts.image}" if not opts.image.startswith("docker://") else opts.image

    if not image_exists(image):
        if not download_image(image):
            raise UserError(f"Unable to create local Singularity image for {image!r}.")

    # XXX TODO: In the future we might want to set rlimits based on cpus and
    # memory, at least on POSIX systems.
    #   -trs, 21 May 2020 (copied from ./native.py on 30 Aug 2022)

    extra_env = {
        **SINGULARITY_CONFIG_ENV,

        # Pass environment into the container via Singularity's bespoke
        # prefixing with SINGULARITYENV_….¹
        #
        # ¹ <https://docs.sylabs.io/guides/3.0/user-guide/environment_and_metadata.html#environment>
        **{f"SINGULARITYENV_{k}": v
            for k, v in extra_env.items()
             if v is not None },
    }

    return exec_or_return([
        "singularity", "run", *SINGULARITY_EXEC_ARGS(),

        # Map directories to bind mount into the container.
        *flatten(("--bind", "%s:%s:%s" % (v.src.resolve(strict = True), docker.mount_point(v), "rw" if v.writable else "ro"))
            for v in opts.volumes
             if v.src is not None),

        # Change the default working directory if requested
        *(("--pwd", str(docker.mount_point(working_volume))) if working_volume else ()),

        str(image_path(image)),
        *argv,
    ], extra_env)


def setup(dry_run: bool = False, force: bool = False) -> SetupStatus:
    if not setup_image(dry_run, force):
        return False

    return True


def setup_image(dry_run: bool = False, force: bool = False) -> bool:
    """
    Create Singularity image if it's not already available locally.

    Though not strictly required, by doing this during setup we avoid the
    initial download and creation on first use instead.
    """
    image = DEFAULT_IMAGE
    path = image_path(image)
    exists = path.exists()

    if not force and exists:
        print(f"Using existing local copy of Singularity image {image}.")
        print(f"  Hint: if you want to ignore this existing local copy, re-run `nextstrain setup` with --force.")
        return True

    if exists:
        print(f"Removing existing local copy of Singularity image {image}…")
        if not dry_run:
            path.unlink()

    update_ok = _update(dry_run)

    if not update_ok:
        return False

    return True


def test_setup() -> SetupTestResults:
    def test_run():
        try:
            capture_output([
                "singularity", "exec", *SINGULARITY_EXEC_ARGS(),

                # XXX TODO: We should test --bind, as that's maybe most likely
                # to be adminstratively disabled, but it's a bit more ceremony
                # to arrange for a reliable dir to bind into the container.
                # Putting it off for now…
                #   -trs, 5 Jan 2023

                # Use the official Busybox image, which is tiny, because
                # the hello-world image doesn't have /bin/sh, which
                # Singularity requires.
                "docker://busybox",

                "/bin/true"
                ], extra_env = SINGULARITY_CONFIG_ENV)
        except:
            return False
        else:
            return True

    yield ("singularity is installed",
            shutil.which("singularity") is not None)

    yield (f"singularity version {singularity_version()} ≥ {SINGULARITY_MINIMUM_VERSION} ({APPTAINER_MINIMUM_VERSION} for Apptainer)",
             singularity_version_at_least(SINGULARITY_MINIMUM_VERSION, apptainer=APPTAINER_MINIMUM_VERSION))

    yield ("singularity works",
            test_run())


def set_default_config() -> None:
    """
    Sets ``core.runner`` to this runner's name (``singularity``).

    Sets ``singularity.image``, if it isn't already set, to the latest
    ``build-*`` image.
    """
    config.set("core", "runner", runner_name(cast(RunnerModule, sys.modules[__name__])))
    config.setdefault("singularity", "image", latest_build_image(DEFAULT_IMAGE))


def update() -> UpdateStatus:
    """
    Download and convert the latest Docker runtime image into a local
    Singularity image.

    Prunes old local Singularity image versions.
    """
    return _update()


def _update(dry_run: bool = False) -> UpdateStatus:
    current_image = DEFAULT_IMAGE
    latest_image  = latest_build_image(current_image)

    if latest_image == current_image:
        print(colored("bold", "Updating Singularity image %s…" % current_image))
    else:
        print(colored("bold", "Updating Singularity image from %s to %s…" % (current_image, latest_image)))
    print()

    # Pull the latest image down
    if not dry_run:
        if not download_image(latest_image):
            return False

        # Update the config file to point to the new image so we use it by
        # default going forward.
        config.set("singularity", "image", latest_image)

    # Clean up unnecessary caches
    print()
    print(colored("bold", "Cleaning up…"))
    print()

    if not dry_run:
        argv = ("singularity", "cache", "clean", "--type=all", "--force")
        env = {
            **os.environ.copy(),
            **SINGULARITY_CONFIG_ENV,
        }

        try:
            subprocess.run(argv, env = env, check = True)
        except (OSError, subprocess.CalledProcessError) as err:
            warn(f"Error running {argv!r}: {err}")
            warn(f"Continuing anyway.")

    # Prune any old images to avoid leaving lots of hidden disk use around.
    print()
    print(colored("bold", "Pruning old images…"))
    print()

    if not dry_run:
        try:
            for old_image in old_build_images(latest_image):
                print(f"Deleting {old_image}")
                old_image.unlink()
        except OSError as error:
            warn()
            warn("Update succeeded, but an error occurred pruning old image versions:")
            warn("  ", error)
            warn()
            warn("Not to worry, we'll try again the next time you run `nextstrain update`.")
            warn()

    return True


def download_image(image: str = DEFAULT_IMAGE) -> bool:
    """
    Download and convert a remote Singularity ``docker://` *image* into a local
    Singularity image using ``singularity build``.
    """
    # We can avoid downloading/conversion for build-* tags (which are static)
    # if the image already exists locally.
    _, tag = split_image_name(docker_image_name(image))

    if docker.is_build_tag(tag) and image_exists(image):
        print(f"Singularity image {image} exists and is up-to-date.")
        return True

    # …but otherwise we must create it fresh.
    path = image_path(image)
    path.parent.mkdir(exist_ok = True, parents = True)

    env = {
        **os.environ.copy(),
        **SINGULARITY_CONFIG_ENV,
    }

    try:
        subprocess.run(
            ["singularity", "build", path, image],
            env   = env,
            check = True)
    except (OSError, subprocess.CalledProcessError):
        return False

    return True


def old_build_images(image: str) -> List[Path]:
    """
    Return a list of local Singularity image paths which were derived from an
    older version of *image* tagged with "build-*".

    If *image* isn't tagged "build-*", nothing is returned out of an abundance
    of caution.  Our "build-*" timestamps use an ISO-8601 timestamp, so oldness
    is determined by sorting lexically.
    """
    repository, tag = split_image_name(docker_image_name(image))

    if not docker.is_build_tag(tag):
        return []

    # List all local images from the same respository, e.g. nextstrain/base.
    images = (IMAGES / repository).glob("*.sif")

    # Return the paths of images with build tags that come before our current
    # build tag, as well as the image with the "latest" tag.  The latter is
    # useful to include because it will likely be out of date when the current
    # tag is a build tag (guaranteed above).
    return [
        path
            for path in images
             if (docker.is_build_tag(path.stem) and path.stem < tag)
             or path.stem == "latest"
    ]


def image_exists(image: str = DEFAULT_IMAGE) -> bool:
    """
    Check if a Singularity ``docker://`` *image* exists locally, returning True
    or False.
    """
    return image_path(image).exists()


def image_path(image: str = DEFAULT_IMAGE) -> Path:
    """
    Return a local path to use for a Singularity ``docker://`` *image*.
    """
    repository, tag = split_image_name(docker_image_name(image))
    return IMAGES / repository / f"{tag}.sif"


def latest_build_image(image: str = DEFAULT_IMAGE) -> str:
    return "docker://" + docker.latest_build_image(docker_image_name(image))


def docker_image_name(image: str = DEFAULT_IMAGE) -> str:
    """
    Convert a Singularity ``docker://`` *image* into a Docker image name.

    >>> docker_image_name("docker://nextstrain/base:latest")
    'nextstrain/base:latest'

    >>> docker_image_name("nextstrain/base")
    Traceback (most recent call last):
        ...
    cli.errors.UserError: Error: Singularity runtime currently only supports docker:// images but got: 'nextstrain/base'
    """
    url = urlsplit(image)

    if url.scheme != "docker":
        raise UserError(f"Singularity runtime currently only supports docker:// images but got: {image!r}")

    return url.netloc + url.path


def versions() -> Iterable[str]:
    if not image_exists():
        yield f"{DEFAULT_IMAGE} (not present)"
        return

    yield f"{DEFAULT_IMAGE} ({image_path()})"

    try:
        yield from run_bash(docker.report_component_versions())
    except (OSError, subprocess.CalledProcessError):
        pass


def run_bash(script: str, image: str = DEFAULT_IMAGE) -> List[str]:
    """
    Run a Bash *script* inside of the container *image*.

    Returns the output of the script as a list of strings.
    """
    return capture_output([
        "singularity", "run", *SINGULARITY_EXEC_ARGS(), image_path(image),
            "bash", "-c", script
    ])


@lru_cache(maxsize = None)
def singularity_version_at_least(min_version: str, *, apptainer: str) -> bool:
    version = singularity_version()

    if not version:
        return False

    if singularity_is_apptainer():
        min_version = apptainer

    return version >= Version(min_version)


@lru_cache(maxsize = None)
def singularity_version() -> Optional[Version]:
    try:
        raw_version = capture_output(["singularity", "version"])[0]
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        return Version(raw_version)
    except InvalidVersion:
        # Singularity sometimes reports a version like 3.11.1-bionic with a
        # (for Python) non-standard suffix ("-bionic"), so try stripping it.
        try:
            return Version(re.sub(r'-.+$', '', raw_version))
        except InvalidVersion:
            return None


@lru_cache(maxsize = None)
def singularity_is_apptainer() -> Optional[bool]:
    singularity = shutil.which("singularity")

    if not singularity:
        return None

    if not Path(singularity).is_symlink():
        return False

    try:
        return Path(os.readlink(singularity)).name == "apptainer"
    except OSError:
        return None

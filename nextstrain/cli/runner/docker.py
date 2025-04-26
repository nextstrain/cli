"""
Run commands inside a container image using Docker.

`Docker <https://docker.com>`__ is a very popular container system
freely-available for all platforms. When you use Docker with the Nextstrain
CLI, you don't need to install any other Nextstrain software dependencies as
validated versions are already bundled into a container image
(`nextstrain/base`_) by the Nextstrain team.


.. _nextstrain/base: https://github.com/nextstrain/docker-base


.. _docker-setup:

Setup
=====

.. hint::
   This is a reference page with brief pointers for set up.  For a more
   comprehensive installation guide, please see `our general Nextstrain
   installation page <https://docs.nextstrain.org/page/install.html>`__.

On macOS, download and install `Docker Desktop`_, also known previously as
"Docker for Mac".

On Linux, install Docker with the standard package manager. For example, on
Ubuntu, you can install Docker with ``sudo apt install docker.io``.

On Windows, install `Docker Desktop`_ with its support for a WSL2 backend.

Once you've installed Docker, proceed with ``nextstrain setup docker``.

This will download compressed image layers totaling about 750 MB in size which
expand to a final on-disk size of about 2 GB.  Transient disk usage during this
process peaks at about 3 GB.  These numbers are current as of August 2023, as
observed on Linux.  Numbers will vary over time, with a tendency to slowly
increase, and vary slightly by OS.

.. _Docker Desktop: https://www.docker.com/products/docker-desktop


.. _docker-config:

Config file variables
=====================

Defaults for the corresponding command line options, specified in the
:doc:`config file </config/file>`.

.. glossary::

    :index:`docker.image <configuration variable; docker.image>`
        Default for ``--image`` when using the Docker runtime, e.g.
        ``nextstrain/base:build-20230623T174208Z``.

        Typically set initially by ``nextstrain setup`` and subsequently by
        ``nextstrain update``.


.. _docker-env:

Environment variables
=====================

.. warning::
    For development only.  You don't need to set these during normal operation.

Defaults for the corresponding command line options, potentially overriding
defaults set by `config file variables`_.

.. envvar:: NEXTSTRAIN_DOCKER_IMAGE

    Default for ``--image`` when using the Docker runtime.
"""

import os
import json
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Iterable, List, cast
from .. import config, env, requests
from ..errors import UserError
from ..types import Env, RunnerModule, SetupStatus, SetupTestResults, SetupTestResultStatus, UpdateStatus
from ..util import warn, colored, capture_output, exec_or_return, runner_name, split_image_name, test_rosetta_enabled
from ..volume import NamedVolume
from ..__version__ import __version__


# The default intentionally omits an explicit "latest" tag so that on the first
# `nextstrain update` it gets pinned in the config file to the most recent
# "build-*" tag.  Users can set an explicit "latest" tag in config to always
# use the most recent image and not pin to "build-*" tags.
DEFAULT_IMAGE = os.environ.get("NEXTSTRAIN_DOCKER_IMAGE") \
             or config.get("docker", "image") \
             or "nextstrain/base"

COMPONENTS = ["augur", "auspice", "fauna"]


class IMAGE_FEATURE(Enum):
    # Auspice ≥1.35.2 necessitated tightly-coupled changes to the image (first
    # present in this tag) and `nextstrain view` (see commit 2754026, first
    # present in the 1.8.0 release).
    compatible_auspice = "build-20190119T045444Z"

    # /nextstrain/env.d support first present.
    envd = "build-20230613T204512Z"

    # AWS Batch: support for volume overlays (i.e. ../ in archive members and
    # file overwriting) in ZIP extraction.
    aws_batch_overlays = "build-20250321T184358Z"


def register_arguments(parser) -> None:
    # Docker development options
    development = parser.add_argument_group(
        "development options for --docker")

    development.set_defaults(docker_args = [])
    development.add_argument(
        "--docker-arg",
        help    = "Additional arguments to pass to `docker run`",
        metavar = "...",
        dest    = "docker_args",
        action  = "append")


def run(opts, argv, working_volume = None, extra_env: Env = {}, cpus: int = None, memory: int = None) -> int:
    assert_volumes_exist(opts.volumes)

    # Check if all our stdio fds (stdin = 0, stdout = 1, stderr = 2) are TTYs.
    # This uses fds explicitly as that's what we (and `docker run`) ultimately
    # care about; not whatever the Python sys.stdin/stdout/stderr filehandles
    # point to.  (They're probably unchanged, but ya never know.)
    stdio_isatty = all(os.isatty(fd) for fd in [0, 1, 2])

    # If the image supports /nextstrain/env.d, then pass any env vars using it
    # so values aren't visible in the container's config (e.g. visible via
    # `docker inspect`).
    if extra_env and image_supports(IMAGE_FEATURE.envd, opts.image):
        # Most of the time this TemporaryDirectory's destructor won't run
        # because we exec into another program.  That's desireable since
        # ultimately the container, shortly after startup, needs to read the
        # files in envd.  The container is configured to delete them when its
        # done, thus leaving an empty directory.  We rely on the OS to
        # periodically clean out TMP (e.g. at boot) to remove the empty
        # directories.  However, if the exec fails, then the destructor *will*
        # run, and we'll clean up the whole thing.
        envd = TemporaryDirectory(prefix = "nextstrain-", suffix = "-env.d")
        opts.volumes.append(NamedVolume("env.d", Path(envd.name)))

        # Write out all env to the dir…
        env.to_dir(Path(envd.name), extra_env)

        # …then clear it from what we pass via the container config and replace
        # it with a flag to delete the contents of the env.d after use.
        extra_env = {"NEXTSTRAIN_DELETE_ENVD": "1"}

    return exec_or_return([
        "docker", "run",
        "--rm",             # Remove the ephemeral container after exiting
        "--interactive",    # Pass through control signals (^C, etc.)

        # Colors, etc.  As documented in `man docker-run`:
        #
        #    The -t option is incompatible with a redirection of the docker
        #    client standard input.
        #
        # so only set it when (at least) our stdin is a TTY.
        #
        # Additionally, we go a step further and condition on _all_ our stdio
        # being a TTY.  Reason being is that under --tty Docker/containerd/runc
        # will read from the container's TTY and send it to `docker run`'s
        # stdout, thus combining the container's stdout + stderr into "our"
        # stdout.  If someone is redirecting our stdout and/or stderr (i.e.
        # it's not a TTY), then they necessarily want separate streams and
        # using --tty will foil that.  More details on this complex issue are
        # in <https://github.com/nextstrain/cli/issues/152>.
        *(["--tty"]
            if stdio_isatty else []),

        # On Unix (POSIX) systems, run the process in the container with the same
        # UID/GID so that file ownership is correct in the bind mount directories.
        # The getuid()/getgid() functions are documented to be only available on
        # Unix systems, not, for example, Windows.
        *(["--user=%d:%d" % (os.getuid(), os.getgid())] if os.name == "posix" else []),

        # Map directories to bind mount into the container.
        *["--volume=%s:%s:%s" % (v.src.resolve(strict = True), mount_point(v), "rw" if v.writable else "ro")
            for v in opts.volumes
             if v.src is not None],

        # Change the default working directory if requested
        *(["--workdir=%s" % mount_point(working_volume)] if working_volume else []),

        # Pass thru any extra environment variables provided by us (not via an env.d)
        *["--env=%s" % name for name, value in extra_env.items() if value is not None],

        # Set resource limits if any
        *(["--cpus=%d" % cpus]
            if cpus is not None else []),

        *(["--memory=%db" % memory]
            if memory is not None else []),

        *opts.docker_args,
        opts.image,
        *argv,
    ], extra_env)


def assert_volumes_exist(volumes: Iterable[NamedVolume]):
    # Ensure all volume source paths exist.  Docker will auto-create missing
    # directories in the path, which, while desirable under some circumstances,
    # doesn't match up well with our use case.  We're aiming to not surprise or
    # confuse the user.
    #
    missing_volumes = [
        vol for vol in volumes
             if (vol.dir and not vol.src.is_dir())
             or not vol.src.exists() ]

    if missing_volumes:
        raise UserError("""
            Error: The path(s) given for the following components do not exist
            or are not directories:

            {missing}
            """, missing = "\n".join(f"    • {vol.name}: {vol.src}" for vol in missing_volumes))


def mount_point(volume: NamedVolume) -> PurePosixPath:
    """
    Determine the mount point of *volume* in the container.
    """
    if volume.name == "bashrc":
        return PurePosixPath("/etc/bash.bashrc")

    return PurePosixPath("/nextstrain", volume.name)


def setup(dry_run: bool = False, force: bool = False) -> SetupStatus:
    if not setup_image(dry_run, force):
        return False

    return True


def setup_image(dry_run: bool = False, force: bool = False) -> bool:
    """
    Download the image if it's not already available locally.

    Though not strictly required, by doing this during setup we avoid the
    initial download on first use instead.
    """
    image = DEFAULT_IMAGE

    if not force and image_exists(image):
        print(f"Using existing local copy of Docker image {image}.")
        print(f"  Hint: if you want to ignore this existing local copy, re-run `nextstrain setup` with --force.")
        return True

    update_ok = _update(dry_run)

    if not update_ok:
        return False

    return True


def test_setup() -> SetupTestResults:
    def test_run():
        try:
            status = subprocess.run(
                ["docker", "run", "--rm", "hello-world"],
                check = True,
                stdout = subprocess.DEVNULL)
        except:
            return False
        else:
            return status.returncode == 0

    def test_memory_limit():
        GiB = 1024**3
        desired = 2 * GiB

        msg = 'containers have access to >%.0f GiB of memory' % (desired / GiB)
        status: SetupTestResultStatus = ...

        if image_exists():
            def int_or_none(x):
                try:
                    return int(float(x))
                except ValueError:
                    return None

            report_memory = """
                awk '/^MemTotal:/ { print $2 * 1024 }' /proc/meminfo
                (cat /sys/fs/cgroup/memory.max || cat /sys/fs/cgroup/memory/memory.limit_in_bytes) 2>/dev/null
            """

            try:
                limits = list(filter(None, map(int_or_none, run_bash(report_memory))))
            except (OSError, subprocess.CalledProcessError):
                pass
            else:
                if limits:
                    limit = min(limits)

                    if limit <= desired:
                        msg += dedent("""

                            Containers appear to be limited to %0.1f GiB of memory. This
                            may not be enough for some Nextstrain builds.  On Windows or
                            a Mac, you can increase the memory available to containers
                            in the Docker preferences.\
                            """ % (limit / GiB))
                        status = None
                    else:
                        msg += " (limit is %.1f GiB)" % (limit / GiB)
                        status = True

        yield (msg, status)

    def test_image_version():
        minimum_tag = IMAGE_FEATURE.compatible_auspice.value

        msg = 'image is new enough for this CLI version'
        status: SetupTestResultStatus = ...

        repository, tag = split_image_name(DEFAULT_IMAGE)

        # If we're using a build tag, regardless of if the image exists
        # locally or not yet, we can say for sure if we're all good or not.
        if is_build_tag(tag):
            status = tag >= minimum_tag

            if not status:
                msg += dedent("""

                    Your copy of the Nextstrain Docker image, %s,
                    is too old for this version of the CLI (%s).  At least
                    version %s of the image is required.

                    Please run `nextstrain update docker` to download a newer
                    image.  Afterwards, run `nextstrain check-setup docker`
                    again and this version check shoud pass.
                    """ % (tag, __version__, minimum_tag))

        # If we're using the "latest" tag and the image doesn't yet exist
        # locally, then the most recent image will be pulled down the first
        # time its needed.  Presumably this will be new enough for the CLI.
        elif tag == "latest" and not image_exists(DEFAULT_IMAGE):
            status = True

        yield (msg, status)

    yield ('docker is installed',
        shutil.which("docker") is not None)

    yield ('docker run works',
        test_run())

    yield from test_memory_limit()

    yield from test_image_version()

    # Rosetta 2 is optional, so convert False (fail) → None (warning)
    yield from ((msg, None if status is False else status)
                  for msg, status
                   in test_rosetta_enabled("Rosetta 2 is enabled for faster execution (optional)"))


def set_default_config() -> None:
    """
    Sets ``core.runner`` to this runner's name (``docker``).

    Sets ``docker.image``, if it isn't already set, to the latest ``build-*``
    image.
    """
    config.set("core", "runner", runner_name(cast(RunnerModule, sys.modules[__name__])))
    config.setdefault("docker", "image", latest_build_image(DEFAULT_IMAGE))


def update() -> UpdateStatus:
    """
    Pull down the latest Docker image build and prune old image versions.
    """
    return _update()


def _update(dry_run: bool = False) -> UpdateStatus:
    current_image = DEFAULT_IMAGE
    latest_image  = latest_build_image(current_image)

    if latest_image == current_image:
        print(colored("bold", "Updating Docker image %s…" % current_image))
    else:
        print(colored("bold", "Updating Docker image from %s to %s…" % (current_image, latest_image)))
    print()

    # Pull the latest image down
    if not dry_run:
        try:
            subprocess.run(
                ["docker", "image", "pull", latest_image],
                check = True)
        except (OSError, subprocess.CalledProcessError):
            return False

        # Update the config file to point to the new image so we use it by default
        # going forward.
        config.set("docker", "image", latest_image)

    # Prune any old images which are now dangling to avoid leaving lots of
    # hidden disk use around.  We don't use `docker image prune` because we
    # want to just remove _our_ dangling images, not all.  We very much don't
    # want to automatically prune unrelated images.
    print()
    print(colored("bold", "Pruning old images…"))
    print()

    if not dry_run:
        try:
            images = dangling_images(latest_image) \
                   + old_build_images(latest_image)

            if images:
                subprocess.run(
                    ["docker", "image", "rm", *images],
                    check = True)
        except (OSError, subprocess.CalledProcessError) as error:
            warn()
            warn("Update succeeded, but an error occurred pruning old image versions:")
            warn("  ", error)
            warn()
            warn("This can occur, for example, if you have a `nextstrain build`,")
            warn("`nextstrain view`, or `nextstrain shell` command still running.")
            warn()
            warn("Not to worry, we'll try again the next time you run `nextstrain update`.")
            warn()

    return True


def image_supports(feature: IMAGE_FEATURE, image: str = DEFAULT_IMAGE) -> bool:
    """
    Test if the given *image* supports a *feature*, i.e. by tag comparison
    against the feature's first release.

    If *image* is tagged ``latest``, either explicitly or implicity, it is
    assumed to have support for all features.
    """
    repository, tag = split_image_name(image)

    return tag == "latest" \
        or (is_build_tag(tag) and tag >= feature.value)


def is_build_tag(tag: str) -> bool:
    """
    Test if the given *tag* looks like one of our build tags.
    """
    return tag.startswith("build-")


def latest_build_image(image_name: str) -> str:
    """
    Query the Docker registry for the latest image tagged "build-*" in the
    given *image_name*'s repository.

    Our "latest" tag always has a "build-*" counterpart.  Using a "build-*" tag
    is better than using the "latest" tag since the former is more descriptive
    and points to a static snapshot instead of a mutable snapshot.

    If the given *image_name* has a tag but it isn't a "build-*" tag, then the
    given *image_name* is returned as-is under the presumption that it points
    to some other mutable snapshot that should be pulled in-place to update.
    This means, for example, that users can opt into tracking the "latest" tag
    by explicitly configuring it as the image to use (versus omitting the
    "latest" tag).

    Examples
    --------

    When a newer "build-*" tag exists, it's returned.

    >>> old = "nextstrain/base:build-20220215T000459Z"
    >>> new = latest_build_image(old)
    >>> _, old_tag = split_image_name(old)
    >>> _, new_tag = split_image_name(new)
    >>> old_tag
    'build-...'
    >>> new_tag
    'build-...'
    >>> new_tag > old_tag
    True

    When a non-build tag is present, it's simply passed through.

    >>> latest_build_image("nextstrain/base:latest")
    'nextstrain/base:latest'

    >>> latest_build_image("nextstrain/base:example")
    'nextstrain/base:example'

    When no tag is present (i.e. implicitly "latest"), a "build-*" tag is
    returned.

    >>> latest_build_image("nextstrain/base")
    'nextstrain/base:build-...'
    """
    def GET(url, **kwargs):
        response = requests.get(url, **kwargs)
        response.raise_for_status()
        return response

    def auth_token(repository: str) -> str:
        url, params = "https://auth.docker.io/token", {
            "scope": "repository:%s:pull" % repository,
            "service": "registry.docker.io",
        }
        return GET(url, params = params).json().get("token")

    def tags(respository: str) -> List[str]:
        url, headers = "https://registry.hub.docker.com/v2/%s/tags/list" % repository, {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            "Authorization": "Bearer %s" % auth_token(repository),
        }
        return GET(url, headers = headers).json().get("tags", [])

    repository, tag = split_image_name(image_name, implicit_latest = False)

    if not tag or is_build_tag(tag):
        build_tags = sorted(filter(is_build_tag, tags(repository)))

        if build_tags:
            return repository + ":" + build_tags[-1]

    return image_name


def old_build_images(name: str) -> List[str]:
    """
    Return a list of local Docker image IDs which are tagged with "build-*" and
    older than the given image *name*.

    If *name* isn't tagged "build-*", nothing is returned out of an abundance
    of caution.  Our "build-*" timestamps use an ISO-8601 timestamp, so oldness
    is determined by sorting lexically.
    """
    repository, tag = split_image_name(name)

    if not is_build_tag(tag):
        return []

    # List all local images from the respository, e.g. nextstrain/base.
    build_images = map(json.loads, capture_output([
        "docker", "image", "ls",
            "--no-trunc",
            "--format={{json .}}",
            repository
    ]))

    # Return the fully-qualified names of images with build tags that come
    # before our current build tag, as well as the image with the "latest" tag.
    # The latter is useful to include because it will likely be out of date
    # when the current tag is a build tag (guaranteed above).
    #
    # Names are used instead of IDs because they won't cause conflicts when an
    # image ID is tagged multiple times: rm-ing the first name will remove only
    # that tag, rm-ing the final name will remove the actual image layers.
    return [
        image["Repository"] + ":" + image["Tag"]
            for image in build_images
             if (is_build_tag(image["Tag"]) and image["Tag"] < tag)
             or image["Tag"] == "latest"
    ]


def dangling_images(name: str) -> List[str]:
    """
    Return a list of local Docker image IDs which are untagged ("dangling") and
    thus likely no longer in use.

    Since dangling images are untagged, this finds images by name using our
    custom org.nextstrain.image.name label.
    """
    name_sans_tag = name.split(":")[0]

    return capture_output([
        "docker", "image", "ls",
            "--no-trunc",
            "--format={{.ID}}",
            "--filter=dangling=true",
            "--filter=label=org.nextstrain.image.name=%s" % name_sans_tag
    ])


def versions() -> Iterable[str]:
    try:
        yield image_version()
    except (OSError, subprocess.CalledProcessError):
        pass

    try:
        if image_exists():
            yield from component_versions()
    except (OSError, subprocess.CalledProcessError):
        pass


def image_version() -> str:
    """
    Print the Docker image name and version.
    """

    # Qualify the name with the "latest" tag if necessary so we only get a
    # single id back.
    qualified_image = DEFAULT_IMAGE

    if ":" not in DEFAULT_IMAGE:
        qualified_image += ":latest"

    image_ids = capture_output([
        "docker", "image", "ls",
            "--format=({{.ID}}, {{.CreatedAt}})", qualified_image])

    assert len(image_ids) <= 1

    # Print the default image name as-is, without the implicit :latest
    # qualification (if any).  The :latest tag is often confusing, as it
    # doesn't mean you have the latest version.  Thus we avoid it.
    #
    # This function (via the version command), may be run before the image is
    # downloaded, so we handle finding no image ids.
    return "%s %s" % (DEFAULT_IMAGE, image_ids[0] if image_ids else "not present")


def component_versions() -> Iterable[str]:
    """
    Print the git ids of the Nextstrain components in the image.
    """
    yield from run_bash(report_component_versions())


def report_component_versions() -> str:
    # It is much faster to spin up a single ephemeral container and read all
    # the versions with a little bash than to do it one-by-one.  It also lets
    # us more easily do fine-grained reporting of presence/absence.
    return """
        for component in %s; do
            if [[ -e /nextstrain/$component/.GIT_ID ]]; then
                echo $component $(</nextstrain/$component/.GIT_ID)
            elif [[ -d /nextstrain/$component ]]; then
                echo $component unknown
            else
                echo $component not present
            fi
        done
    """ % " ".join(COMPONENTS)


def run_bash(script: str, image: str = DEFAULT_IMAGE) -> List[str]:
    """
    Run a Bash *script* inside of the container *image*.

    Returns the output of the script as a list of strings.
    """
    return capture_output([
        "docker", "run", "--rm", image,
            "bash", "-c", script
    ])


def image_exists(image: str = DEFAULT_IMAGE) -> bool:
    """
    Check if a Docker *image* exists locally, returning True or False.
    """
    try:
        subprocess.run(
            ["docker", "image", "inspect", image],
            check = True,
            stdout = subprocess.DEVNULL,
            stderr = subprocess.DEVNULL)
    except:
        return False
    else:
        return True

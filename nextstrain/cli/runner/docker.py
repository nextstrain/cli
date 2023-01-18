"""
Run commands inside a container image using Docker.
"""

import os
import json
import requests
import shutil
import subprocess
from pathlib import PurePosixPath
from textwrap import dedent
from typing import Iterable, List
from .. import hostenv, config
from ..errors import UserError
from ..types import RunnerSetupStatus, RunnerTestResults, RunnerTestResultStatus, RunnerUpdateStatus
from ..util import warn, colored, capture_output, exec_or_return, split_image_name
from ..volume import store_volume, NamedVolume
from ..__version__ import __version__


# The default intentionally omits an explicit "latest" tag so that on the first
# `nextstrain update` it gets pinned in the config file to the most recent
# "build-*" tag.  Users can set an explicit "latest" tag in config to always
# use the most recent image and not pin to "build-*" tags.
DEFAULT_IMAGE = os.environ.get("NEXTSTRAIN_DOCKER_IMAGE") \
             or config.get("docker", "image") \
             or "nextstrain/base"

COMPONENTS = ["augur", "auspice", "fauna", "sacra"]


def register_arguments(parser) -> None:
    # Docker development options
    #
    # XXX TODO: Consider prefixing all of these with --docker-* at some point,
    # depending on how other image-based runners (like Singularity) pan out.
    # For now, I think it's better to do nothing than to prospectively rename.
    # Renaming means maintaining the old names as deprecated alternatives for a
    # while anyway, so we might as well just keep using what we have until
    # we're forced to change.
    #   -trs, 15 August 2018
    development = parser.add_argument_group(
        "development options for --docker")

    development.set_defaults(volumes = [])

    for name in COMPONENTS:
        development.add_argument(
            "--" + name,
            help    = "Replace the image's copy of %s with a local copy" % name,
            metavar = "<dir>",
            action  = store_volume(name))

    development.set_defaults(docker_args = [])
    development.add_argument(
        "--docker-arg",
        help    = "Additional arguments to pass to `docker run`",
        metavar = "...",
        dest    = "docker_args",
        action  = "append")


def run(opts, argv, working_volume = None, extra_env = {}, cpus: int = None, memory: int = None) -> int:
    assert_volumes_exist(opts.volumes)

    # Check if all our stdio fds (stdin = 0, stdout = 1, stderr = 2) are TTYs.
    # This uses fds explicitly as that's what we (and `docker run`) ultimately
    # care about; not whatever the Python sys.stdin/stdout/stderr filehandles
    # point to.  (They're probably unchanged, but ya never know.)
    stdio_isatty = all(os.isatty(fd) for fd in [0, 1, 2])

    # The getuid()/getgid() functions are documented to be only available on
    # Unix systems, not, for example, Windows.
    #
    # We use this weird getattr() construction in order to appease Mypy, which
    # otherwise has trouble with platform-specific attributes on the "os"
    # module.
    uid = getattr(os, "getuid", lambda: None)()
    gid = getattr(os, "getgid", lambda: None)()

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
        *(["--user=%d:%d" % (uid, gid)] if uid and gid else []),

        # Map directories to bind mount into the container.
        *["--volume=%s:%s:%s" % (v.src.resolve(strict = True), mount_point(v), "rw" if v.writable else "ro")
            for v in opts.volumes
             if v.src is not None],

        # Change the default working directory if requested
        *(["--workdir=/nextstrain/%s" % working_volume.name] if working_volume else []),

        # Pass through certain environment variables
        *["--env=%s" % name for name in hostenv.forwarded_names],

        # Plus any extra environment variables provided by us
        *["--env=%s" % name for name in extra_env.keys()],

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


def setup(dry_run: bool = False, force: bool = False) -> RunnerSetupStatus:
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


def test_setup() -> RunnerTestResults:
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
        status: RunnerTestResultStatus = ...

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

        return [(msg, status)]

    def test_image_version():
        minimum_tag = "build-20190119T045444Z"

        msg = 'image is new enough for this CLI version'
        status: RunnerTestResultStatus = ...

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

                    Please run `nextstrain update` to download a newer image.
                    Afterwards, run `nextstrain check-setup` again and this
                    version check shoud pass.
                    """ % (tag, __version__, minimum_tag))

        # If we're using the "latest" tag and the image doesn't yet exist
        # locally, then the most recent image will be pulled down the first
        # time its needed.  Presumably this will be new enough for the CLI.
        elif tag == "latest" and not image_exists(DEFAULT_IMAGE):
            status = True

        return [(msg, status)]

    return [
        ('docker is installed',
            shutil.which("docker") is not None),
        ('docker run works',
            test_run()),
        *test_memory_limit(),
        *test_image_version()
    ]


def set_default_config() -> None:
    """
    Sets ``docker.image``, if it isn't already set, to the latest ``build-*``
    image.
    """
    config.setdefault("docker", "image", latest_build_image(DEFAULT_IMAGE))


def update() -> RunnerUpdateStatus:
    """
    Pull down the latest Docker image build and prune old image versions.
    """
    return _update()


def _update(dry_run: bool = False) -> RunnerUpdateStatus:
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

"""
Run commands inside a container image using Docker.
"""

import os
import json
import requests
import shutil
import subprocess
from textwrap import dedent
from typing import List, Tuple
from .. import runner, hostenv, config
from ..types import RunnerTestResults
from ..util import warn, colored, capture_output, exec_or_return
from ..volume import store_volume


DEFAULT_IMAGE = os.environ.get("NEXTSTRAIN_DOCKER_IMAGE") \
             or config.get("docker", "image") \
             or "nextstrain/base"

COMPONENTS = ["sacra", "fauna", "augur", "auspice"]


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

    development.add_argument(
        "--image",
        help    = "Container image in which to run the pathogen build",
        metavar = "<name>",
        default = DEFAULT_IMAGE)

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


def run(opts, argv, working_volume = None) -> int:
    # Ensure all volume source paths exist.  Docker will auto-create missing
    # directories in the path, which, while desirable under some circumstances,
    # doesn't match up well with our use case.  We're aiming to not surprise or
    # confuse the user.
    #
    missing_volumes = [ vol for vol in opts.volumes if not vol.src.is_dir() ]

    if missing_volumes:
        warn("Error: The path(s) given for the following components do not exist")
        warn("or are not directories:")
        warn()
        for vol in missing_volumes:
            warn("    • %s: %s" % (vol.name, vol.src))
        return 1

    return exec_or_return([
        "docker", "run",
        "--rm",             # Remove the ephemeral container after exiting
        "--tty",            # Colors, etc.
        "--interactive",    # Pass through control signals (^C, etc.)

        # On Unix (POSIX) systems, run the process in the container with the same
        # UID/GID so that file ownership is correct in the bind mount directories.
        # The getuid()/getgid() functions are documented to be only available on
        # Unix systems, not, for example, Windows.
        *(["--user=%d:%d" % (os.getuid(), os.getgid())] if os.name == "posix" else []),

        # Map directories to bind mount into the container.
      *["--volume=%s:/nextstrain/%s" % (v.src.resolve(), v.name)
            for v in opts.volumes
             if v.src is not None],

        # Change the default working directory if requested
        *(["--workdir=/nextstrain/%s" % working_volume.name] if working_volume else []),

        # Pass through certain environment variables
      *["--env=%s" % name for name in hostenv.forwarded_names],

        *opts.docker_args,
        opts.image,
        *argv,
    ])


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
        status = ...

        if image_exists():
            report_memory = """
                awk '/^MemTotal:/ { print $2 * 1024 }' /proc/meminfo
                cat /sys/fs/cgroup/memory/memory.limit_in_bytes
            """

            try:
                total, cgroup = map(int, run_bash(report_memory))
            except ValueError:
                # If for some reason we can't get both values...
                pass
            else:
                limit = cgroup if cgroup < total else total

                if limit <= desired:
                    msg += dedent("""

                        Containers appear to be limited to %0.1f GiB of memory. This
                        may not be enough for some Nextstrain builds.  On Windows or
                        a Mac, you can increase the memory available to containers
                        in the Docker preferences.\
                        """ % (limit / GiB))
                    status = None
                else:
                    status = True

        return [(msg, status)]

    return [
        ('docker is installed',
            shutil.which("docker") is not None),
        ('docker run works',
            test_run()),
        *test_memory_limit()
    ]


def update() -> bool:
    """
    Pull down the latest Docker image build and prune old image versions.
    """
    current_image = DEFAULT_IMAGE
    latest_image  = latest_build_image(current_image)

    if latest_image == current_image:
        print(colored("bold", "Updating Docker image %s…" % current_image))
    else:
        print(colored("bold", "Updating Docker image from %s to %s…" % (current_image, latest_image)))
    print()

    # Pull the latest image down
    try:
        subprocess.run(
            ["docker", "image", "pull", latest_image],
            check = True)
    except subprocess.CalledProcessError:
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

    try:
        images = dangling_images(current_image) \
               + old_build_images(current_image)

        if images:
            subprocess.run(
                ["docker", "image", "rm", *images],
                check = True)
    except subprocess.CalledProcessError as error:
        warn()
        warn("Update succeeded, but an error occurred pruning old image versions:")
        warn("  ", error)
        warn()

    return True


def split_image_name(name: str) -> Tuple[str, str]:
    """
    Split the image *name* into a (repository, tag) tuple.
    """
    if ":" in name:
        repository, tag = name.split(":", maxsplit = 2)
    else:
        repository, tag = name, "latest"

    return (repository, tag)


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

    If the given *image_name* is not tagged "build-*" or "latest" (implicitly
    or explicitly), then the given *image_name* is returned as-is under the
    presumption that it points to some other mutable snapshot that should be
    pulled in-place to update.
    """
    def auth_token(repository: str) -> str:
        url, params = "https://auth.docker.io/token", {
            "scope": "repository:%s:pull" % repository,
            "service": "registry.docker.io",
        }
        return requests.get(url, params = params).json().get("token")

    def tags(respository: str) -> List[str]:
        url, headers = "https://registry.hub.docker.com/v2/%s/tags/list" % repository, {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            "Authorization": "Bearer %s" % auth_token(repository),
        }
        return requests.get(url, headers = headers).json().get("tags", [])

    repository, tag = split_image_name(image_name)

    if tag == "latest" or is_build_tag(tag):
        build_tags = sorted(filter(is_build_tag, tags(repository)))

        if build_tags:
            return repository + ":" + build_tags[-1]
        else:
            return repository + ":latest"
    else:
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


def print_version() -> None:
    print_image_version()
    print_component_versions()


def print_image_version() -> None:
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
            "--format={{.ID}} ({{.CreatedAt}})", qualified_image])

    assert len(image_ids) <= 1

    # Print the default image name as-is, without the implicit :latest
    # qualification (if any).  The :latest tag is often confusing, as it
    # doesn't mean you have the latest version.  Thus we avoid it.
    #
    # This function (via the version command), may be run before the image is
    # downloaded, so we handle finding no image ids.
    print("%s docker image %s" % (DEFAULT_IMAGE, image_ids[0] if image_ids else "not present"))


def print_component_versions() -> None:
    """
    Print the git ids of the Nextstrain components in the image.
    """

    # It is much faster to spin up a single ephemeral container and read all
    # the versions with a little bash than to do it one-by-one.  It also lets
    # us more easily do fine-grained reporting of presence/absence.
    report_versions = """
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

    versions = run_bash(report_versions)

    for version in versions:
        print("  " + version)


def run_bash(script: str, image: str = DEFAULT_IMAGE) -> List[str]:
    """
    Run a Bash *script* inside of the container *image*.

    Returns the output of the script as a list of strings.
    """
    return capture_output([
        "docker", "run", "--rm", "-it", image,
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
    except subprocess.CalledProcessError:
        return False
    else:
        return True

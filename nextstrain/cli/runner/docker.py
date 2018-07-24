"""
Run commands inside a container image using Docker.
"""

import os
import shutil
import argparse
import subprocess
from collections import namedtuple
from pathlib import Path
from ..util import warn


DEFAULT_IMAGE = "nextstrain/base"


def store_volume(volume_name):
    """
    Generates and returns an argparse.Action subclass for storing named volume
    tuples.

    Multiple argparse arguments can use this to cooperatively accept source
    path definitions for named volumes.

    Each named volume is stored as a namedtuple (name, src).  The tuple is
    stored on the options object under the volume's name (modified to replace
    slashes with underscores), as well as added to a shared list of volumes,
    accessible via the "volumes" attribute on the options object.

    For convenient path manipulation and testing, the "src" value is stored as
    a Path object.
    """
    volume = namedtuple("volume", ("name", "src"))

    class store(argparse.Action):
        def __call__(self, parser, namespace, values, option_strings = None):
            # Add the new volume to the list of volumes
            volumes    = getattr(namespace, "volumes", [])
            new_volume = volume(volume_name, Path(values))
            setattr(namespace, "volumes", [*volumes, new_volume])

            # Allow the new volume to be found by name on the opts object
            setattr(namespace, volume_name.replace('/', '_'), new_volume)

    return store


def register_arguments(parser, exec=None, volumes=[]):
    # Unpack exec parameter into the command and everything else
    (exec_cmd, *exec_args) = exec

    # Development options
    development = parser.add_argument_group(
        "development options",
        "These should generally be unnecessary unless you're developing build images.")

    development.add_argument(
        "--image",
        help    = "Container image in which to run the pathogen build",
        metavar = "<name>",
        default = DEFAULT_IMAGE)

    development.add_argument(
        "--exec",
        help    = "Program to exec inside the build container",
        metavar = "<prog>",
        default = exec_cmd)

    development.set_defaults(volumes = [])

    for name in volumes:
        development.add_argument(
            "--" + name,
            help    = "Replace the image's copy of %s with a local copy" % name,
            metavar = "<dir>",
            action  = store_volume(name))

    development.add_argument(
        "--docker-arg",
        help    = "Additional arguments to pass to `docker run`",
        metavar = "...",
        dest    = "docker_args",
        action  = "append")

    # Optional exec arguments
    parser.set_defaults(exec_args = exec_args)
    parser.set_defaults(extra_exec_args = [])

    if ... in exec_args:
        parser.add_argument(
            "extra_exec_args",
            help    = "Additional arguments to pass to the executed build program",
            metavar = "...",
            nargs   = argparse.REMAINDER)


def run(opts):
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

    if opts.docker_args is None:
        opts.docker_args = []

    argv = [
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

        # Pass through credentials as environment variables
        "--env=RETHINK_HOST",
        "--env=RETHINK_AUTH_KEY",

        *opts.docker_args,
        opts.image,
        opts.exec,
        *replace_ellipsis(opts.exec_args, opts.extra_exec_args)
    ]

    try:
        subprocess.run(argv, check = True)
    except subprocess.CalledProcessError as e:
        warn("Error running %s, exited %d" % (e.cmd, e.returncode))
        return e.returncode
    else:
        return 0


def replace_ellipsis(items, elided_items):
    """
    Replaces any Ellipsis items (...) in a list, if any, with the items of a
    second list.
    """
    return [
        y for x in items
          for y in (elided_items if x is ... else [x])
    ]


def test_setup():
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

    return [
        ('docker is installed',
            shutil.which("docker") is not None),
        ('docker run works',
            test_run()),
    ]


def update():
    try:
        status = subprocess.run(
            ["docker", "image", "pull", DEFAULT_IMAGE],
            check = True)
    except:
        return False
    else:
        return status.returncode == 0

"""
Runs a pathogen build in an ephemeral container.

The build directory should contain a Snakefile, which will be run with
snakemake inside the container.

Docker is the currently the only supported container system.  It must be
installed and configured, which you can test by running:

    docker run --rm hello-world

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from Docker itself so that we can more seamlessly use other
container systems in the future as desired or necessary.
"""

import os
import subprocess
import argparse
from ..util import warn


COMPONENTS = ["sacra", "fauna", "augur"]


def register_parser(subparser):
    parser = subparser.add_parser("build", help = "Run pathogen build")
    parser.description = __doc__

    # Development options
    development = parser.add_argument_group(
        "development options",
        "These should generally be unnecessary unless you're developing build images.")

    development.add_argument(
        "--image",
        help    = "Container image in which to run the pathogen build",
        metavar = "<name>",
        default = "quay.io/nextstrain/base")

    development.add_argument(
        "--exec",
        help    = "Program to exec inside the build container",
        metavar = "<prog>",
        default = "snakemake")

    for component in COMPONENTS:
        development.add_argument(
            "--" + component,
            help    = "Replace the image's copy of %s with a local copy" % component,
            metavar = "<dir>")

    development.add_argument(
        "--docker-arg",
        help    = "Additional arguments to pass to `docker run`",
        metavar = "...",
        dest    = "docker_args",
        action  = "append")

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>")

    parser.add_argument(
        "extra_args",
        help    = "Additional arguments to pass to the executed build program",
        metavar = "...",
        nargs   = argparse.REMAINDER)

    return parser


def run(opts):
    volumes = [
        ('build', opts.directory),
        *[(c, getattr(opts, c)) for c in COMPONENTS]
    ]

    argv = [
        "docker", "run",
        "--rm",
        "--tty",            # Colors, etc.
        "--interactive",    # Pass through control signals (^C, etc.)
        "--user=%d:%d" % (os.getuid(), os.getgid()),
      *["--volume=%s:/nextstrain/%s" % (os.path.abspath(src), dst)
            for dst, src in volumes
             if src is not None],
        *opts.docker_args,
        opts.image,
        opts.exec,
        *opts.extra_args
    ]

    try:
        subprocess.run(argv, check = True)
    except subprocess.CalledProcessError as e:
        warn("Error running %s, exited %d" % (e.cmd, e.returncode))
        return e.returncode
    else:
        return 0

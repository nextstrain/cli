"""
Start a new shell inside the Nextstrain containerized build environment to
run ad-hoc commands and perform debugging.

The shell runs inside a container, which requires Docker.  Run `nextstrain
check-setup` to check if Docker is installed and works.
"""

from ..runner import docker
from ..volume import store_volume


def register_parser(subparser):
    parser = subparser.add_parser("shell", help = "Start a new shell in the build environment")
    parser.description = __doc__

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        action  = store_volume("build"))

    # Runner options
    docker.register_arguments(
        parser,
        exec    = ["bash", "--login", ...],
        volumes = ["sacra", "fauna", "augur", "auspice"])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    return docker.run(opts)

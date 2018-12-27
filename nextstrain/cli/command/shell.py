"""
Start a new shell inside the Nextstrain containerized build environment to
run ad-hoc commands and perform debugging.

The shell runs inside a container, which requires Docker.  Run `nextstrain
check-setup` to check if Docker is installed and works.
"""

from .. import runner
from ..argparse import add_extended_help_flags
from ..runner import docker
from ..util import colored, resolve_path, warn
from ..volume import store_volume


def register_parser(subparser):
    """
    %(prog)s [options] <directory> [...]
    %(prog)s --help
    """

    parser = subparser.add_parser("shell", help = "Start a new shell in the build environment", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        action  = store_volume("build"))

    # Register runner flags and arguments; only Docker is supported for now
    # since a "native" shell doesn't make any sense.
    runner.register_runners(
        parser,
        exec    = ["bash", "--login", ...],
        runners = [docker])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    print(colored("bold", "Entering the Nextstrain build environment"))
    print()

    if opts.volumes:
        print(colored("bold", "Mapped volumes:"))

        # This is more tightly coupled to the Docker runner than I'd like (i.e.
        # assuming /nextstrain/…), but right now that's the only runner this
        # command supports (and the only one it makes sense to).
        #   -trs, 25 Sept 2018
        for volume in opts.volumes:
            print("  /nextstrain/%s is from %s" % (volume.name, resolve_path(volume.src)))

        print()

    print(colored("bold", 'Run the command "exit" to leave the build environment.'))
    print()

    return runner.run(opts, working_volume = opts.build)

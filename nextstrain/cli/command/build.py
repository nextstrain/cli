"""
Runs a pathogen build in an ephemeral container.

The build directory should contain a Snakefile, which will be run with
snakemake inside the container.

Docker is the currently the only supported container system.  It must be
installed and configured, which you can test by running:

    nextstrain check-setup

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from Docker itself so that we can more seamlessly use other
container systems in the future as desired or necessary.
"""

from .. import runner
from ..util import warn
from ..volume import store_volume


def register_parser(subparser):
    parser = subparser.add_parser("build", help = "Run pathogen build")
    parser.description = __doc__

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        action  = store_volume("build"))

    # Register runner flags and arguments
    runner.register_runners(parser, exec = ["snakemake", ...])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    return runner.run(opts, working_volume = opts.build)

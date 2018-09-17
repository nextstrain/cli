"""
Runs a pathogen build in the Nextstrain build environment.

The build directory should contain a Snakefile, which will be run with
snakemake.

The default build environment is inside an ephemeral Docker container which has
all the necessary Nextstrain components available.  You may instead run the
build in the native ambient environment by passing the --native flag, but all
dependencies must already be installed and configured.  For larger builds, you
may want to use the --aws-batch flag to launch jobs on AWS Batch instead of
running locally (if the required AWS resources are configured in your AWS
account).

You can test if Docker, native, or AWS Batch build environments are properly
supported on your computer by running:

    nextstrain check-setup

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from provisioning a build environment, so that running builds
is as easy as possible.  It also lets us more seamlessly make environment
changes in the future as desired or necessary.
"""

from .. import runner
from ..argparse import add_extended_help_flags
from ..util import warn
from ..volume import store_volume


def register_parser(subparser):
    """
    %(prog)s [options] <directory> [...]
    %(prog)s --help
    """

    parser = subparser.add_parser("build", help = "Run pathogen build", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

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

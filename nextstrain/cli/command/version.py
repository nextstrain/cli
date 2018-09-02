"""
Prints the version of the Nextstrain CLI.
"""

from ..__version__ import __version__
from .. import __package__ as __top_package__
from ..runner import all_runners

def register_parser(subparser):
    parser = subparser.add_parser("version", help = "Show version information")

    parser.add_argument(
        "--verbose",
        help   = "Show versions of individual Nextstrain components in the image",
        action = "store_true")

    return parser


def run(opts):
    print(__top_package__, __version__)

    if opts.verbose:
        for runner in all_runners:
            runner.print_version()

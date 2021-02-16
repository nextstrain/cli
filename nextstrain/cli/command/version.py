"""
Prints the version of the Nextstrain CLI.
"""

import sys
from textwrap import indent
from ..__version__ import __version__
from .. import __package__ as __top_package__
from ..runner import all_runners
from ..util import runner_name

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
        print()
        print("Python")
        print("  " + sys.executable)
        print(indent(sys.version, "  "))
        print()

        print("Runners")
        for runner in all_runners:
            print("  " + runner_name(runner))
            versions = list(runner.versions())
            if versions:
                for version in versions:
                    print("    " + version)
            else:
                print("    unknown")
            print()

"""
Prints the version of the Nextstrain CLI.
"""

import sys
from textwrap import indent
from ..__version__ import __version__
from ..runner import all_runners, default_runner
from ..util import runner_name, standalone_installation

def register_parser(subparser):
    parser = subparser.add_parser("version", help = "Show version information")

    parser.add_argument(
        "--verbose",
        help   = "Show versions of individual Nextstrain components in each runtime",
        action = "store_true")

    return parser


def run(opts):
    print("Nextstrain CLI", __version__, "(standalone)" if standalone_installation() else "")

    if opts.verbose:
        print()
        print("Python")
        print("  " + sys.executable)
        print(indent(sys.version, "  "))
        print()

        print("Runners")
        for runner in all_runners:
            print("  " + runner_name(runner), "(default)" if runner is default_runner else "")
            versions = list(runner.versions())
            if versions:
                for version in versions:
                    print("    " + version)
            else:
                print("    unknown")
            print()

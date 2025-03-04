"""
Prints the version of the Nextstrain CLI.
"""

import sys
from textwrap import indent
from ..__version__ import __version__
from ..pathogens import all_pathogen_versions_by_name, every_pathogen_default_by_name
from ..runner import all_runners, default_runner
from ..util import runner_name, standalone_installation

def register_parser(subparser):
    parser = subparser.add_parser("version", help = "Show version information")

    parser.add_argument(
        "--verbose",
        help   = "Show versions of each runtime, plus select individual Nextstrain components within, and versions of each pathogen, including URLs",
        action = "store_true")

    parser.add_argument(
        "--pathogens",
        help   = "Show pathogen versions; implied by --verbose",
        action = "store_true")

    parser.add_argument(
        "--runtimes",
        help   = "Show runtime versions; implied by --verbose",
        action = "store_true")

    return parser


def run(opts):
    print("Nextstrain CLI", __version__, "(standalone)" if standalone_installation() else "")

    if opts.verbose:
        print()
        print("Python")
        print("  " + sys.executable)
        print(indent(sys.version, "  "))

    if opts.runtimes or (opts.verbose and not opts.pathogens):
        print()
        print("Runtimes")
        for i, runner in enumerate(all_runners):
            if i != 0:
                print()
            print("  " + runner_name(runner), "(default)" if runner is default_runner else "")
            versions = iter(runner.versions())
            version = next(versions, None)
            if version:
                print("    " + version)
            else:
                print("    unknown")
            if opts.verbose:
                for version in versions:
                    print("    " + version)

    if opts.pathogens or (opts.verbose and not opts.runtimes):
        print()
        print("Pathogens")
        if pathogens := all_pathogen_versions_by_name():
            defaults = every_pathogen_default_by_name(pathogens)

            for i, (name, versions) in enumerate(pathogens.items()):
                if i != 0:
                    print()
                print("  " + name)
                for version in versions.values():
                    is_default = version == defaults.get(name)
                    print("    " + str(version) + (f"={version.url or ''}" if opts.verbose else ""), "(default)" if is_default else "")
                    if opts.verbose:
                        print("      " + str(version.path))
        else:
            print("  (none)")

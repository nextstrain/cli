"""
Nextstrain command-line tool
"""


import sys
import argparse
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter
from types    import SimpleNamespace

from .argparse    import register_commands, register_default_command
from .command     import build, view, deploy, remote, shell, update, check_setup, version
from .__version__ import __version__


class HelpFormatter(ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter):
    pass


def run(args):
    """
    Command-line entrypoint to the nextstrain-cli package, called by the
    `nextstrain` program.
    """
    parser = ArgumentParser(
        prog            = "nextstrain",
        description     = __doc__,
        formatter_class = HelpFormatter,
    )

    # Maintain these manually for now while the list is very small.  If we need
    # to support pluggable commands or command discovery, we can switch to
    # using the "entry points" system:
    #    https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins
    #
    commands = [
        build,
        view,
        deploy,
        remote,
        shell,
        update,
        check_setup,
        version,
    ]

    register_default_command(parser)
    register_commands(parser, commands)
    register_version_alias(parser)

    opts = parser.parse_args(args)
    return opts.__command__.run(opts)


def register_version_alias(parser):
    """
    Add --version as a (hidden) alias for the version command.

    It's not uncommon to blindly run a command with --version as the sole
    argument, so its useful to make that Just Work.
    """

    class run_version_command(argparse.Action):
        def __call__(self, *args, **kwargs):
            opts = SimpleNamespace(verbose = False)
            sys.exit( version.run(opts) )

    parser.add_argument(
        "--version",
        nargs  = 0,
        help   = argparse.SUPPRESS,
        action = run_version_command)

"""
Nextstrain command-line interface (CLI)

The `nextstrain` program and its subcommands aim to provide a consistent way to
run and visualize pathogen builds and access Nextstrain components like Augur
and Auspice across computing environments such as Docker, Conda, and AWS Batch.
"""


import sys
import argparse
from argparse import ArgumentParser
from types    import SimpleNamespace

from .argparse    import HelpFormatter, register_commands, register_default_command
from .command     import build, view, deploy, remote, shell, update, check_setup, login, logout, whoami, version
from .errors      import NextstrainCliError
from .util        import warn
from .__version__ import __version__


def run(args):
    """
    Command-line entrypoint to the nextstrain-cli package, called by the
    `nextstrain` program.
    """
    parser = make_parser()
    opts = parser.parse_args(args)

    try:
        return opts.__command__.run(opts)

    except NextstrainCliError as error:
        warn(error)
        return 1


def make_parser():
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
        login,
        logout,
        whoami,
        version,
    ]

    register_default_command(parser)
    register_commands(parser, commands)
    register_version_alias(parser)

    return parser


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

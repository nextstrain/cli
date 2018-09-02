"""
Nextstrain command-line tool
"""


import sys
import argparse
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter
from types    import SimpleNamespace

from .command     import build, view, deploy, shell, update, check_setup, version
from .util        import format_usage
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


def register_default_command(parser):
    """
    Sets the default command to run when none is provided.
    """
    def run(x):
        parser.print_help()
        return 2

    # Using a namespace object to mock a module with a run() function
    parser.set_defaults( __command__ = SimpleNamespace(run = run) )


def register_commands(parser, commands):
    """
    Lets each command module register a subparser.
    """
    subparsers = parser.add_subparsers(title = "commands")

    for cmd in commands:
        subparser = cmd.register_parser(subparsers)
        subparser.set_defaults( __command__ = cmd )

        # Ensure all subparsers format like the top-level parser
        subparser.formatter_class = parser.formatter_class

        # Default usage message to the docstring of register_parser()
        if not subparser.usage and cmd.register_parser.__doc__:
            subparser.usage = format_usage(cmd.register_parser.__doc__)

        # Default long description to the docstring of the command
        if not subparser.description and cmd.__doc__:
            subparser.description = cmd.__doc__


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

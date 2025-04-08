"""
Nextstrain command-line interface (CLI)

The `nextstrain` program and its subcommands aim to provide a consistent way to
run and visualize pathogen builds and access Nextstrain components like Augur
and Auspice across computing platforms such as Docker, Conda, Singularity, and
AWS Batch.

Run `nextstrain <command> --help` for usage information about each command.
See <:doc:`/index`> for more documentation.
"""


import sys
import traceback
from argparse import ArgumentParser, Action, SUPPRESS
from textwrap import dedent

from .argparse    import HelpFormatter, register_commands, register_default_command
from .command     import all_commands
from .debug       import DEBUGGING
from .errors      import NextstrainCliError, UsageError
from .util        import warn
from .__version__ import __version__ # noqa: F401 (for re-export)


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
        exit_status = 1

        if DEBUGGING:
            traceback.print_exc()
        else:
            if isinstance(error, UsageError):
                warn(opts.__parser__.format_usage())
                exit_status = 2

            warn(error)

        return exit_status

    except AssertionError:
        traceback.print_exc()
        warn("\n")
        warn(dedent("""\
            An error occurred (see above) that likely indicates a bug in the
            Nextstrain CLI.

            To report this, please open a new issue and include the error above:
                <https://github.com/nextstrain/cli/issues/new/choose>
            """))
        return 1


def make_parser():
    parser = ArgumentParser(
        prog            = "nextstrain",
        description     = __doc__,
        formatter_class = HelpFormatter,
    )

    register_default_command(parser)
    register_commands(parser, all_commands)
    register_version_alias(parser)

    return parser


def register_version_alias(parser):
    """
    Add --version as a (hidden) alias for the version command.

    It's not uncommon to blindly run a command with --version as the sole
    argument, so its useful to make that Just Work.
    """

    class run_version_command(Action):
        def __call__(self, *args, **kwargs):
            # Go thru parse_args() rather than creating an opts Namespace
            # ourselves and passing it directly to version.run() so that the
            # version command's options pick up their normal defaults.
            opts = parser.parse_args(["version"])
            sys.exit( opts.__command__.run(opts) )

    parser.add_argument(
        "--version",
        nargs  = 0,
        help   = SUPPRESS,
        action = run_version_command)

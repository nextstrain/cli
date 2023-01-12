"""
Nextstrain command-line interface (CLI)

The `nextstrain` program and its subcommands aim to provide a consistent way to
run and visualize pathogen builds and access Nextstrain components like Augur
and Auspice across computing platforms such as Docker, Conda, and AWS Batch.

Run `nextstrain <command> --help` for usage information about each command.
See <:doc:`/`> for more documentation.
"""


import sys
import traceback
from argparse import ArgumentParser, Action, SUPPRESS
from textwrap import dedent
from types    import SimpleNamespace

from .argparse    import HelpFormatter, register_commands, register_default_command
from .command     import build, view, deploy, remote, shell, update, setup, check_setup, login, logout, whoami, version, init_shell, authorization, debugger
from .debug       import DEBUGGING
from .errors      import NextstrainCliError
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
        if DEBUGGING:
            traceback.print_exc()
        else:
            warn(error)
        return 1

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
        setup,
        check_setup,
        login,
        logout,
        whoami,
        version,
        init_shell,
        authorization,
        debugger,
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

    class run_version_command(Action):
        def __call__(self, *args, **kwargs):
            opts = SimpleNamespace(verbose = False)
            sys.exit( version.run(opts) )

    parser.add_argument(
        "--version",
        nargs  = 0,
        help   = SUPPRESS,
        action = run_version_command)

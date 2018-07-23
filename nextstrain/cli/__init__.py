"""
Nextstrain command-line tool
"""


from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter
from types    import SimpleNamespace

from .command     import build, view, update, check_setup, version
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
        update,
        check_setup,
        version,
    ]

    register_default_command(parser)
    register_commands(parser, commands)

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

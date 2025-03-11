"""
Custom helpers for extending the behaviour of argparse standard library.
"""
import os
import sys
from argparse import Action, ArgumentDefaultsHelpFormatter, ArgumentParser, ArgumentTypeError, SUPPRESS, _SubParsersAction # pyright: ignore[reportPrivateUsage]
from itertools import chain, takewhile
from pathlib import Path
from textwrap import indent as indent_text
from types import SimpleNamespace
from typing import Iterable, Optional, Tuple
from .rst import rst_to_text
from .types import RunnerModule
from .util import format_usage, runner_module


# The standard argument group title for non-positional arguments.  See
# <https://github.com/python/cpython/pull/23858> and
# <https://bugs.python.org/issue9694>.
OPTIONS_TITLE = "options" if sys.version_info >= (3, 10) else "optional arguments"


# Include this in an argument help string to suppress the automatic appending
# of the default value by argparse.ArgumentDefaultsHelpFormatter.  This works
# because the automatic appending is conditional on the presence of %(default),
# so we include it but then format it as a zero-length string .0s.  🙃
#
# Another solution would be to add an extra attribute to the argument (the
# argparse.Action instance) and then subclass ArgumentDefaultsHelpFormatter to
# condition on that new attribute, but that seems more brittle.
SKIP_AUTO_DEFAULT_IN_HELP = "%(default).0s"


class HelpFormatter(ArgumentDefaultsHelpFormatter):
    def __init__(self, prog, indent_increment = 2, max_help_position = 24, width = None):
        # Ignore terminal size, unlike standard argparse, as the readability of
        # paragraphs of text suffers at wide widths.  Instead, default to 78
        # columns (80 wide - 2 column gutter), but let that be overridden by an
        # explicit COLUMNS variable or reduced by a smaller actual terminal.
        if width is None:
            try:
                width = int(os.environ["COLUMNS"])
            except (KeyError, ValueError):
                try:
                    width = min(os.get_terminal_size().columns, 80) - 2
                except (AttributeError, OSError):
                    width = 80 - 2

        super().__init__(prog, indent_increment, max_help_position, width)

    # Based on argparse.RawDescriptionHelpFormatter's implementation
    def _fill_text(self, text, width, indent):
        return indent_text(rst_to_text(text, width), prefix=indent)

    # Based on argparse.RawTextHelpFormatter's implementation
    def _split_lines(self, text, width):
        # Render to rST here so rST gets control over wrapping/line breaks.
        return rst_to_text(text, width).splitlines()

    # Emit blank lines between arguments for better readability.  It might seem
    # simpler to override _join_parts() instead, but that's called from two
    # places and we only want to join on newlines for one of those places.
    def add_arguments(self, actions):
        for i, action in enumerate(actions):
            if i != 0:
                # Use " \n" to avoid a completely empty line (e.g. "\n") for
                # the sake ShowBriefHelp.truncate_help()'s heuristic.
                self._add_item(str, [" \n"])

            self.add_argument(action)


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

        # No need to worry about reference cycles of subparser to itself.
        # CPython's GC uses automatic reference counting complemented with
        # traversal-based reachability detection that can handle cycles.¹
        # Other implementations may not, but we largely don't care about those,
        # and taking a big step back, our processes here just don't live long
        # enough for the cycle to be a memory issue (plus it's just one cycle,
        # not recreated over and over again in a hot loop).
        #   -trs, 24 August 2023
        #
        # ¹ <https://docs.python.org/3.11/reference/datamodel.html#index-2>
        subparser.set_defaults( __command__ = cmd, __parser__ = subparser )

        # Ensure all subparsers format like the top-level parser
        subparser.formatter_class = parser.formatter_class

        # Default usage message to the docstring of register_parser()
        if not subparser.usage and cmd.register_parser.__doc__:
            subparser.usage = format_usage(cmd.register_parser.__doc__)

        # Default long description to the docstring of the command
        if not subparser.description and cmd.__doc__:
            subparser.description = cmd.__doc__

        # Recursively register any subcommands
        if getattr(subparser, "subcommands", None):
            register_commands(subparser, subparser.subcommands)

            # If a command with subcommands doesn't have its own run()
            # function, then print its help when called without a subcommand.
            if not getattr(cmd, "run", None):
                register_default_command(subparser)


def add_extended_help_flags(parser):
    """
    Add --help/-h and --help-all flags to the ArgumentParser.

    Aims to make the default --help output more approachable by truncating it
    to the most common options.  The full help is available using --help-all.
    """
    parser.add_argument(
        "--help", "-h",
        help    = "Show a brief help message of common options and exit",
        action  = ShowBriefHelp)

    parser.add_argument(
        "--help-all",
        help    = "Show a full help message of all options and exit",
        action  = "help")


class ShowBriefHelp(Action):
    def __init__(self, option_strings, help = None, **kwargs):
        super().__init__(
            option_strings,
            help    = help,
            nargs   = 0,
            dest    = SUPPRESS,
            default = SUPPRESS)

    def __call__(self, parser, namespace, values, option_string = None):
        """
        Print a truncated version of the standard full help from argparse.
        """
        full_help  = parser.format_help()
        brief_help = self.truncate_help(full_help)

        print(brief_help)

        if len(brief_help) < len(full_help):
            print("Run again with --help-all instead to see more options.")

        parser.exit()

    def truncate_help(self, full_help):
        """
        Truncate the full help after the standard "options" (or "optional
        arguments") listing and before any custom argument groups.
        """
        seen_optional_arguments_heading = False

        def before_extra_argument_groups(line):
            """
            Return True until we've seen the empty line following the
            hard-coded optional arguments group (that is, all non-positional
            arguments which aren't in another explicit group).
            """
            nonlocal seen_optional_arguments_heading

            if not seen_optional_arguments_heading:
                if line == f"{OPTIONS_TITLE}:\n":
                    seen_optional_arguments_heading = True

            return not seen_optional_arguments_heading \
                or line != "\n"

        lines = full_help.splitlines(keepends = True)

        return "".join(list(takewhile(before_extra_argument_groups, lines)))


class AppendOverwriteDefault(Action):
    """
    Similar to the core argparse ``append`` action, but overwrites the argument
    ``default``, if any, instead of appending to it.

    Thus, the ``default`` value is not included when the option is given and
    may be a non-list value if desired.
    """
    def __call__(self, parser, namespace, value, option_string = None):
        current = getattr(namespace, self.dest, None)

        if current is parser.get_default(self.dest) or current is None:
            current = []

        setattr(namespace, self.dest, [*current, value])


def runner_module_argument(name: str) -> RunnerModule:
    """
    Wraps :py:func:`runner_module` for friendlier error handling.

    Converts :py:exc:`ValueError` to :py:exc:`ArgumentTypeError`, which lets
    :py:mod:`argparse` emit a nice error message when this function is used as
    an argument ``type``.

    >>> runner_module_argument("docker") # doctest: +ELLIPSIS
    <module 'cli.runner.docker' from '...'>

    >>> runner_module_argument("AWS-Batch") # doctest: +ELLIPSIS
    <module 'cli.runner.aws_batch' from '...'>

    >>> runner_module_argument("AWS Batch") # doctest: +ELLIPSIS
    <module 'cli.runner.aws_batch' from '...'>

    >>> runner_module_argument("native") # doctest: +ELLIPSIS
    <module 'cli.runner.ambient' from '...'>

    >>> runner_module_argument("invalid")
    Traceback (most recent call last):
        ...
    argparse.ArgumentTypeError: invalid runtime name: 'invalid'; valid names are: 'docker', 'conda', 'singularity', 'ambient', 'aws-batch'

    >>> runner_module_argument("Invalid Name")
    Traceback (most recent call last):
        ...
    argparse.ArgumentTypeError: invalid runtime name: 'Invalid Name' (normalized to 'invalid-name'); valid names are: 'docker', 'conda', 'singularity', 'ambient', 'aws-batch'
    """
    try:
        return runner_module(name)
    except ValueError as err:
        raise ArgumentTypeError(*err.args) from err


def DirectoryPath(value: str) -> Path:
    """
    Argument ``type`` function which enforces a path is a directory that
    exists.

    Raises :py:exc:`ArgumentTypeError` if not a directory, which lets
    :py:mod:`argparse` emit a nice error message.
    """
    path = Path(value)

    if not path.is_dir():
        raise ArgumentTypeError(f"not a directory: {value}")

    return path


def walk_commands(parser: ArgumentParser, command: Optional[Tuple[str, ...]] = None) -> Iterable[Tuple[Tuple[str, ...], ArgumentParser]]:
    if command is None:
        command = (parser.prog,)

    yield command, parser

    subparsers = chain.from_iterable(
        action.choices.items()
            for action in parser._actions
             if isinstance(action, _SubParsersAction))

    visited = set()

    for subname, subparser in subparsers:
        if subparser in visited:
            continue

        visited.add(subparser)

        yield from walk_commands(subparser, (*command, subname))

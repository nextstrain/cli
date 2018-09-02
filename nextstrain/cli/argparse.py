"""
Custom helpers for extending the behaviour of argparse standard library.
"""

from argparse import Action, SUPPRESS
from itertools import takewhile


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
        Truncate the full help after the standard "optional arguments" listing
        and before any custom argument groups.
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
                if line == "optional arguments:\n":
                    seen_optional_arguments_heading = True

            return not seen_optional_arguments_heading \
                or line != "\n"

        lines = full_help.splitlines(keepends = True)

        return "".join(list(takewhile(before_extra_argument_groups, lines)))

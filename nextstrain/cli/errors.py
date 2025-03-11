"""
Exception classes for internal use.
"""
from textwrap import dedent


class NextstrainCliError(Exception):
    """Exception base class for all custom :mod:`nextstrain.cli` exceptions."""
    pass

class InternalError(NextstrainCliError):
    pass

class UserError(NextstrainCliError):
    """
    Error intended for display to the user, e.g. an error aiming to be clear,
    friendly, and, if possible, actionable.
    """
    def __init__(self, message, *args, **kwargs):
        # Remove leading newlines, trailing whitespace, and then indentation
        # to better support nicely-formatted """multi-line strings""".
        formatted_message = dedent(message.lstrip("\n").rstrip()).format(*args, **kwargs)

        super().__init__("Error: " + formatted_message)

class UsageError(UserError):
    """
    Prints brief command usage before the error message.
    """
    pass

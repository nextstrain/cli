"""
Exception classes for internal use.
"""

class NextstrainCliError(Exception):
    """Exception base class for all custom :mod:`nextstrain.cli` exceptions."""
    pass

class UserError(NextstrainCliError):
    def __init__(self, message, *args, **kwargs):
        super().__init__("Error: " + message, *args, **kwargs)

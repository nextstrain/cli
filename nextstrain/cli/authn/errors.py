"""
Authentication errors.
"""
from ..aws.cognito.srp import NewPasswordRequiredError # noqa: F401 (NewPasswordRequiredError is for re-export)

class IdPError(Exception):
    """Error from IdP during authentication."""
    pass

class NotAuthorizedError(IdPError):
    """Not Authorized response during authentication."""
    pass

class TokenError(Exception):
    """Error when verifying tokens."""
    pass

class MissingTokenError(TokenError):
    """
    No token provided but one is required.

    Context is the kind of token ("use") that was missing.
    """
    pass

class ExpiredTokenError(TokenError):
    """
    Token is expired.

    Context is the kind of token ("use") that was missing.
    """
    pass

class InvalidUseError(TokenError):
    """
    The "use" of the token does not match the expected value.

    May indicate an accidental token swap.
    """
    pass

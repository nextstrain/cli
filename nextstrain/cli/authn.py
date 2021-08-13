"""
Authentication routines.
"""
from functools import partial
from typing import Dict, List, Optional

from . import config
from .errors import UserError
from .aws import cognito


# Section to use in config.SECRETS file
CONFIG_SECTION = "authn"

# Public ids.  Client id is specific to the CLI.
COGNITO_USER_POOL_ID = "us-east-1_Cg5rcTged"
COGNITO_CLIENT_ID    = "2vmc93kj4fiul8uv40uqge93m5"

CognitoSession = partial(cognito.Session, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID)


class User:
    """
    Data class holding information about a user.
    """
    username: str
    groups: List[str]
    email: str

    def __init__(self, id_claims: dict):
        self.username = id_claims["cognito:username"]
        self.groups   = id_claims["cognito:groups"]
        self.email    = id_claims["email"]


def login(username: str, password: str) -> User:
    """
    Authenticates the given *username* and *password*.

    Returns a :class:`User` object with information about the logged in user
    when successful.

    Raises a :class:`UserError` if authentication fails.
    """
    session = CognitoSession()

    try:
        session.authenticate(username, password)

    except cognito.NewPasswordRequiredError:
        raise UserError("Password change required.  Please login to Nextstrain.org first.")

    except cognito.NotAuthorizedError as error:
        raise UserError(f"Login failed: {error}")

    _save_tokens(session)
    print(f"Credentials saved to {config.SECRETS}.")

    assert session.id_claims

    return User(session.id_claims)


def logout():
    """
    Remove locally-saved credentials.

    The authentication tokens are not invalidated and will remain valid until
    they expire.  This does not contact Cognito and other devices/clients are
    not logged out of Nextstrain.org.
    """
    if config.remove(CONFIG_SECTION, config.SECRETS):
        print(f"Credentials removed from {config.SECRETS}.")
        print("Logged out.")
    else:
        print("Not logged in.")


def current_user() -> Optional[User]:
    """
    Information about the currently logged in user, if any.

    Returns a :class:`User` object after validating saved credentials, renewing
    and updating them if necessary.

    Returns ``None`` if there are no saved credentials or if they're unable to
    be automatically renewed.
    """
    session = CognitoSession()
    tokens = _load_tokens()

    try:
        try:
            session.verify_tokens(**tokens)

        except cognito.ExpiredTokenError:
            session.renew_tokens(refresh_token = tokens.get("refresh_token"))
            _save_tokens(session)
            print("Renewed login credentials.")

    except (cognito.TokenError, cognito.NotAuthorizedError):
        return None

    assert session.id_claims

    return User(session.id_claims)


def _load_tokens() -> Dict[str, Optional[str]]:
    """
    Load id, access, and refresh tokens (if any) from the local secrets file.
    """
    def load(name):
        return config.get(CONFIG_SECTION, name, fallback = None, path = config.SECRETS)

    return {
        "id_token":      load("id_token"),
        "access_token":  load("access_token"),
        "refresh_token": load("refresh_token") }


def _save_tokens(session: cognito.Session):
    """
    Save id, access, and refresh tokens from the :class:`cognito.Session`
    *session* to the local secrets file.
    """
    def save(name, value):
        return config.set(CONFIG_SECTION, name, value, path = config.SECRETS)

    save("id_token",      session.id_token)
    save("access_token",  session.access_token)
    save("refresh_token", session.refresh_token)

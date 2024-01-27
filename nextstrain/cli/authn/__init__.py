"""
Authentication routines.

Primarily for OpenID Connect 1.0 / OAuth 2.0 identity providers, with a bit of
AWS Cognito-specific support.

Baked in is an assumption of a nextstrain.org-like remote which provides us
with dynamic provider and client configuration via a discovery request.
"""
from sys import stderr
from typing import Callable, Dict, List, Optional, Tuple

from .. import config
from ..errors import UserError
from ..url import Origin
from . import errors
from .configuration import client_configuration
from .session import Session


# Section (or section prefix) to use in config.SECRETS file
CONFIG_SECTION = "authn"


class User:
    """
    Data class holding information about a user.
    """
    origin: Origin
    username: str
    groups: List[str]
    email: Optional[str]
    http_authorization: str

    def __init__(self, origin: Origin, session: Session):
        assert origin
        assert origin == session.origin
        self.origin = origin

        client_config = client_configuration(origin)
        username_claim = client_config["id_token_username_claim"]
        groups_claim   = client_config["id_token_groups_claim"]

        assert session.id_claims
        self.username = session.id_claims[username_claim]
        self.groups   = session.id_claims.get(groups_claim, [])
        self.email    = session.id_claims.get("email")

        self.http_authorization = f"Bearer {session.id_token}"


def login(origin: Origin, credentials: Optional[Callable[[], Tuple[str, str]]] = None) -> User:
    """
    Authenticates with *origin* by using a (username, password) tuple obtained
    by calling *credentials* or, when *credentials* is omitted, via an
    interactive flow thru the user's web browser.

    Returns a :class:`User` object with information about the logged in user
    when successful.

    Raises a :class:`UserError` if authentication fails.
    """
    assert origin

    session = Session(origin)

    try:
        if credentials:
            if not session.can_authenticate_with_password:
                raise UserError(f"""
                    Remote {origin} does not support logging in
                    with a username and password.

                    Omit specifying any username or password to login via a
                    web browser instead.
                    """)
            session.authenticate_with_password(*credentials())
        else:
            if not session.can_authenticate_with_browser:
                raise UserError(f"""
                    Remote {origin} does not support logging in
                    via a web browser.

                    Specify a username (e.g. with --username) to login with a
                    password instead.
                    """)
            session.authenticate_with_browser()

    except errors.NewPasswordRequiredError:
        raise UserError(f"Password change required.  Please visit {origin} and login there first.")

    except errors.NotAuthorizedError as error:
        raise UserError(f"Login failed: {error}")

    _save_tokens(origin, session)
    print(f"Credentials for {origin} saved to {config.SECRETS}.", file = stderr)

    return User(origin, session)


def renew(origin: Origin) -> Optional[User]:
    """
    Renews existing saved credentials for *origin*, if possible.

    Returns a :class:`User` object with renewed information about the logged in
    user when successful.

    Returns ``None`` if there are no saved credentials or if they're unable to
    be automatically renewed.
    """
    assert origin

    session = Session(origin)
    tokens = _load_tokens(origin)
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        return None

    try:
        session.renew_tokens(refresh_token = refresh_token)

    except (errors.TokenError, errors.NotAuthorizedError):
        return None

    _save_tokens(origin, session)
    print(f"Renewed login credentials for {origin} in {config.SECRETS}.", file = stderr)

    return User(origin, session)


def logout(origin: Origin):
    """
    Remove locally-saved credentials.

    The authentication tokens are not invalidated and will remain valid until
    they expire.  This does not contact the origin's IdP (e.g. Cognito) and
    other devices/clients are not logged out of Nextstrain.org.
    """
    assert origin

    if config.remove(_config_section(origin), config.SECRETS):
        print(f"Credentials for {origin} removed from {config.SECRETS}.", file = stderr)
        print(f"Logged out of {origin}.", file = stderr)
    else:
        print(f"Not logged in to {origin}.", file = stderr)


def logout_all():
    """
    Remove **all** locally-saved credentials.

    Equivalent to calling :func:`logout` on all origins found in the secrets
    file.
    """
    with config.write_lock():
        secrets = config.load(config.SECRETS)

        sections = [
            (section, _parse_section(section))
                for section in secrets
                 if _parse_section(section) ]

        if sections:
            for section, origin in sections:
                del secrets[section]
                print(f"Credentials for {origin} removed from {config.SECRETS}.", file = stderr)
                print(f"Logged out of {origin}.", file = stderr)

            config.save(secrets, config.SECRETS)
        else:
            print(f"Not logged in to any remotes.", file = stderr)


def current_user(origin: Origin) -> Optional[User]:
    """
    Information about the currently logged in user for *origin*, if any.

    Returns a :class:`User` object after validating saved credentials, renewing
    and updating them if necessary.

    Returns ``None`` if there are no saved credentials or if they're unable to
    be automatically renewed.
    """
    assert origin

    tokens = _load_tokens(origin)

    # Short-circuit if we don't have any tokens to speak of.  Avoids trying to
    # fetch authn metadata from the remote origin.
    if all(token is None for token in tokens.values()):
        return None

    session = Session(origin)

    try:
        try:
            session.verify_tokens(**tokens)

        except errors.ExpiredTokenError:
            session.renew_tokens(refresh_token = tokens.get("refresh_token"))
            _save_tokens(origin, session)
            print(f"Renewed login credentials for {origin} in {config.SECRETS}.", file = stderr)

    except (errors.TokenError, errors.NotAuthorizedError):
        return None

    return User(origin, session)


def _load_tokens(origin: Origin) -> Dict[str, Optional[str]]:
    """
    Load id, access, and refresh tokens (if any) from the local secrets file.
    """
    assert origin

    with config.read_lock():
        secrets = config.load(config.SECRETS)
        section = _config_section(origin)

        def load(name):
            if section in secrets:
                return secrets[section].get(name, None)
            else:
                return None

        return {
            "id_token":      load("id_token"),
            "access_token":  load("access_token"),
            "refresh_token": load("refresh_token") }


def _save_tokens(origin: Origin, session: Session):
    """
    Save id, access, and refresh tokens from the :class:`Session`
    *session* to the local secrets file.
    """
    assert origin
    assert origin == session.origin

    with config.write_lock():
        secrets = config.load(config.SECRETS)
        section = _config_section(origin)

        if section not in secrets:
            secrets.add_section(section)

        assert session.id_token
        assert session.access_token
        assert session.refresh_token

        secrets[section]["id_token"]      = session.id_token
        secrets[section]["access_token"]  = session.access_token
        secrets[section]["refresh_token"] = session.refresh_token

        config.save(secrets, config.SECRETS)


def _config_section(origin: Origin) -> str:
    assert origin

    # In the future, consider removing this special-casing of
    # nextstrain.org—that is, stop using [authn] and have it use [authn
    # https://nextstrain.org] like other remotes—by detecting the old section
    # and automatically migrating it from the former to the latter.  For now,
    # I'm inclined not to worry about it.  Using [authn] for now also means
    # that older and newer versions of the CLI can co-exist with the same
    # secrets file.
    #   -trs, 20 Nov 2023
    if origin == "https://nextstrain.org":
        return CONFIG_SECTION
    return f"{CONFIG_SECTION} {origin}"


def _parse_section(section: str) -> Optional[Origin]:
    if section == CONFIG_SECTION:
        return Origin("https://nextstrain.org")
    elif section.startswith(CONFIG_SECTION + " "):
        return Origin(section.split(" ", 1)[1])
    else:
        return None

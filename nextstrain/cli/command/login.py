"""
Logs in a Nextstrain.org Groups user, storing their credentials locally.
"""
import getpass
from pycognito import Cognito
from typing import Dict
from .. import config
from ..errors import AuthnError, UserError


COGNITO_CLIENT_ID='2vmc93kj4fiul8uv40uqge93m5'
COGNITO_USER_POOL_ID='us-east-1_Cg5rcTged'


def register_parser(subparser):
    parser = subparser.add_parser("login", help = "Login as a Nextstrain.org Groups user")

    register_arguments(parser)

    return parser


def register_arguments(parser):
    parser.add_argument(
        "--no-prompt",
        help    = "Log into nextstrain.org without prompting for credentials",
        action  = 'store_true')

    return parser


def run(opts):
    print("Logging into nextstrain.org...")

    tokens = {
        k : config.get('login', k, fallback=None, path=config.SECRETS)
            for k in [ 'username' ,'access_token', 'id_token', 'refresh_token' ]
    }

    if not tokens['username']:
        if opts.no_prompt:
            raise AuthnError("No Nextstrain.org Groups credentials found.")

        login()
        return 0

    try:
        authenticate_without_password(tokens)

    except Exception as e:
        error_message = "Failed to log in with saved credentials: %s" % e
        if opts.no_prompt:
            raise AuthnError(error_message)

        print(error_message)
        print()
        login()
        return 0

    print("Logged into nextstrain.org as %s" % tokens['username'])
    print("Log out with `nextstrain logout`")


def authenticate_without_password(tokens: Dict[str, str]):
    """
    Authenticates a Nextstrain.org Groups user with the provided *tokens*.
    """
    cognito = Cognito(COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID,
        username=tokens['username'],
        id_token=tokens['id_token'],
        refresh_token=tokens['refresh_token'],
        access_token=tokens['access_token'])

    # The Cognito.authenticate() method, which performs token verification,
    # requires a password. We do not want to store passwords locally or prompt
    # a Nextstrain.org Groups user for a password each time they login
    # (otherwise, what's the point of storing credentials locally?).
    #
    # So, as a workaround for authenticating AWS SRP tokens, utilize the
    # undocumented Cognito.verify_token() method which will throw an error if
    # the given token is invalid.
    cognito.verify_token(tokens['id_token'], 'id_token', 'id')

    # The Cognito.check_token() method verifies the access token, so there's no
    # need to use the .verify_token() workaround here.
    access_token_expired = cognito.check_token()
    if access_token_expired:
        print("Replacing expired tokens...")
        save_credentials(cognito, config.SECRETS)


def login():
    """
    With user input, logs a Nextstrain Groups user into nextstrain.org.

    Failed login attempts are printed to stdout and result in a non-zero exit
    code.

    Saves SRP credentials to a local secrets path.
    """
    username = input('Username: ')
    password = getpass.getpass()

    try:
        cognito = Cognito(COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, username=username)
        cognito.authenticate(password=password)

    except Exception as e:
        raise UserError("Failed to login: %s" % e)

    print("Logged in successfully!")

    save_credentials(cognito, config.SECRETS)


def save_credentials(c: Cognito, path):
    """
    Saves SRP tokens from the given *cognito* instance to a local file at *path*
    under a 'login' header.
    """
    tokens = {
        'username'      : c.username,
        'id_token'      : c.id_token,
        'refresh_token' : c.refresh_token,
        'access_token'  : c.access_token,
        'token_type'    : c.token_type
    }

    for key in tokens:
        config.set('login', key, tokens[key], path)

    print("Credentials saved to %s" % path)

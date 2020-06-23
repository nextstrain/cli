"""
Logs in a Nextstrain.org Groups user, storing their credentials locally.
"""
import getpass
from pycognito import Cognito
from typing import Dict
from .. import config
from ..errors import UserError


COGNITO_CLIENT_ID='2vmc93kj4fiul8uv40uqge93m5'
COGNITO_USER_POOL_ID='us-east-1_Cg5rcTged'


def register_parser(subparser):
    parser = subparser.add_parser("login", help = "Login as a Nextstrain.org Groups user")

    return parser


def run(opts):
    print("Logging into nextstrain.org...")

    login()


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

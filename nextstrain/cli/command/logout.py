"""
Logs out a Nextstrain.org Groups user, deleting their locally-stored
credentials.
"""
from .. import config


def register_parser(subparser):
    parser = subparser.add_parser("logout", help = "Logout a Nextstrain.org Groups user")

    return parser


def run(opts):
    config.clear('login', config.SECRETS)
    print("Credentials removed from %s" % config.SECRETS)
    print('Logged out.')

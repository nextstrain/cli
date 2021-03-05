"""
Log out of Nextstrain.org by deleting locally-saved credentials.

The authentication tokens are removed but not invalidated, so if you used them
outside of the `nextstrain` command, they will remain valid until they expire.

Other devices/clients (like your web browser) are not logged out of
Nextstrain.org.
"""
from ..authn import logout


def register_parser(subparser):
    parser = subparser.add_parser("logout", help = "Log out of Nextstrain.org")
    return parser


def run(opts):
    logout()

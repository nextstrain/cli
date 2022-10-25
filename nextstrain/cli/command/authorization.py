"""
Produce an Authorization header appropriate for nextstrain.org's web API.

This is a development tool unnecessary for normal usage.  It's useful for
directly making API requests to nextstrain.org with ``curl`` or similar
commands.  For example::

    curl -si https://nextstrain.org/whoami \\
        --header "Accept: application/json" \\
        --header @<(nextstrain authorization)

Exits with an error if no one is logged in.
"""
from ..authn import current_user
from ..errors import UserError


def register_parser(subparser):
    parser = subparser.add_parser("authorization", help = "Print an HTTP Authorization header")
    return parser


def run(opts):
    user = current_user()

    if not user:
        raise UserError("Not logged in.")

    print(f"Authorization: {user.http_authorization}")

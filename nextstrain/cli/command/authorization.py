"""
Produce an Authorization header appropriate for the web API of nextstrain.org
(and other remotes).

This is a development tool unnecessary for normal usage.  It's useful for
directly making API requests to nextstrain.org (and other remotes) with `curl`
or similar commands.  For example::

    curl -si https://nextstrain.org/whoami \\
        --header "Accept: application/json" \\
        --header @<(nextstrain authorization)

Exits with an error if no one is logged in.
"""
from inspect import cleandoc
from ..errors import UserError
from ..remote import parse_remote_path


def register_parser(subparser):
    parser = subparser.add_parser("authorization", help = "Print an HTTP Authorization header")

    parser.add_argument(
        "remote",
        help    = cleandoc("""
            Remote URL for which to produce an Authorization header.  Expects
            URLs like the remote source/destination URLs used by the
            `nextstrain remote` family of commands.  Only the domain name
            (technically, the origin) of the URL is required/used, but a full
            URL may be specified.
            """),
        metavar = "<remote-url>",
        nargs   = "?",
        default = "nextstrain.org")

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote)
    assert url.origin

    user = remote.current_user(url.origin)

    if not user:
        raise UserError(f"Not logged in to {url.origin}.")

    print(f"Authorization: {user.http_authorization}")

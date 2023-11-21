"""
Log out of Nextstrain.org (and other remotes) by deleting locally-saved
credentials.

The authentication tokens are removed but not invalidated, so if you used them
outside of the `nextstrain` command, they will remain valid until they expire.

Other devices/clients (like your web browser) are not logged out of
Nextstrain.org (or other remotes).
"""
from inspect import cleandoc
from ..remote import parse_remote_path


def register_parser(subparser):
    parser = subparser.add_parser("logout", help = "Log out of Nextstrain.org (and other remotes)")

    parser.add_argument(
        "remote",
        help    = cleandoc("""
            Remote URL to log out of, like the remote source/destination URLs
            used by the `nextstrain remote` family of commands.  Only the
            domain name (technically, the origin) of the URL is required/used,
            but a full URL may be specified.
            """),
        metavar = "<remote-url>",
        nargs   = "?",
        default = "nextstrain.org")

    # XXX TODO: Supporting `nextstrain logout --all` would be nice.
    #   -trs, 15 Nov 2023

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote)
    assert url.origin

    remote.logout(url.origin)

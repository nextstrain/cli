"""
Log out of Nextstrain.org (and other remotes) by deleting locally-saved
credentials.

The authentication tokens are removed but not invalidated, so if you used them
outside of the `nextstrain` command, they will remain valid until they expire.

Other devices/clients (like your web browser) are not logged out of
Nextstrain.org (or other remotes).
"""
from inspect import cleandoc
from .. import authn
from ..remote import parse_remote_path


def register_parser(subparser):
    """
    %(prog)s [<remote-url>]
    %(prog)s --all
    %(prog)s --help
    """
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

    parser.add_argument(
        "--all",
        help = "Log out of all remotes for which there are locally-saved credentials",
        action = "store_true")

    return parser


def run(opts):
    if opts.all:
        authn.logout_all()

    else:
        remote, url = parse_remote_path(opts.remote)
        assert url.origin

        remote.logout(url.origin)

"""
Show information about the logged-in user for Nextstrain.org (and other
remotes).

The username, email address (if available), and Nextstrain Groups memberships
of the currently logged-in user are shown.

Exits with an error if no one is logged in.
"""
from inspect import cleandoc
from ..errors import UserError
from ..remote import parse_remote_path


def register_parser(subparser):
    parser = subparser.add_parser("whoami", help = "Show information about the logged-in user")

    parser.add_argument(
        "remote",
        help    = cleandoc("""
            Remote URL for which to show the logged-in user.  Expects URLs like
            the remote source/destination URLs used by the `nextstrain remote`
            family of commands.  Only the domain name (technically, the origin)
            of the URL is required/used, but a full URL may be specified.
            """),
        metavar = "<remote-url>",
        nargs   = "?",
        default = "nextstrain.org")

    # XXX TODO: Supporting `nextstrain whoami --all` would be nice.
    #   -trs, 15 Nov 2023

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote)
    assert url.origin

    user = remote.current_user(url.origin)

    if not user:
        raise UserError(f"Not logged in to {url.origin}.")

    print(f"# Logged into {user.origin} as…")
    print(f"username: {user.username}")
    if user.email:
        print(f"email: {user.email}")
    print(f"groups: {format_groups(user)}")


def format_groups(user):
    if user.groups:
        return "".join(f"\n  - {g}" for g in sorted(user.groups))
    else:
        return "\n  # (none)"

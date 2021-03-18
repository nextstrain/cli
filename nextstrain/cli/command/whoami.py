"""
Show information about the logged-in user.

The username, email address, and Nextstrain Groups memberships of the currently
logged-in user are shown.

Exits with an error if no one is logged in.
"""
from textwrap import dedent
from ..authn import current_user
from ..errors import UserError


def register_parser(subparser):
    parser = subparser.add_parser("whoami", help = "Show information about the logged-in user")
    return parser


def run(opts):
    user = current_user()

    if not user:
        raise UserError("Not logged in.")

    print(f"username: {user.username}")
    print(f"email: {user.email}")
    print(f"groups: {format_groups(user)}")


def format_groups(user):
    if user.groups:
        return "".join(f"\n  - {g}" for g in sorted(user.groups))
    else:
        return "\n  # (none)"

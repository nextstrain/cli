"""
Log into Nextstrain.org and save credentials for later use.

The first time you log in, you'll be prompted for your Nextstrain.org username
and password.  After that, locally-saved authentication tokens will be used and
automatically renewed as needed when you run other `nextstrain` commands
requiring log in.  You can also re-run this `nextstrain login` command to force
renewal if you want.  You'll only be prompted for your username and password if
the locally-saved tokens are unable to be renewed or missing entirely.

If you log out of Nextstrain.org on other devices/clients (like your web
browser), you may be prompted to re-enter your username and password by this
command sooner than usual.

Your password itself is never saved locally.
"""
from getpass import getpass
from ..authn import current_user, login
from ..errors import UserError


def register_parser(subparser):
    parser = subparser.add_parser("login", help = "Log into Nextstrain.org")

    parser.add_argument(
        "--no-prompt",
        help    = "Don't prompt for a username/password; "
                  "only verify and renew existing tokens, if possible, "
                  "otherwise error.  Useful for scripting.",
        action  = 'store_true')

    return parser


def run(opts):
    user = current_user()

    if not user:
        if opts.no_prompt:
            raise UserError("No Nextstrain.org credentials found and --no-prompt prevents interactive login.")

        print("Logging into Nextstrain.org…")
        print()

        try:
            username = input('Username: ')
            password = getpass()
        except (EOFError, KeyboardInterrupt):
            print()
            raise UserError("Aborted by user input")
        else:
            print()

        user = login(username, password)
        print()

    print(f"Logged into nextstrain.org as {user.username}.")
    print("Log out with `nextstrain logout`.")

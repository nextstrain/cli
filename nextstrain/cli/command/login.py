"""
Log into Nextstrain.org (and other remotes) and save credentials for later use.

The first time you log in to a remote you'll be prompted to authenticate via
your web browser or, if you provide a username (e.g. with --username), for your
Nextstrain.org password.  After that, locally-saved authentication tokens will
be used and automatically renewed as needed when you run other `nextstrain`
commands requiring log in.  You can also re-run this `nextstrain login` command
to force renewal if you want.  You'll only be prompted to reauthenticate (via
your web browser or username/password) if the locally-saved tokens are unable
to be renewed or missing entirely.

If you log out of Nextstrain.org (or other remotes) on other devices/clients
(like your web browser), you may be prompted to reauthenticate by this command
sooner than usual.

Your username and password themselves are never saved locally.
"""
from functools import partial
from getpass import getpass
from inspect import cleandoc
from os import environ
from shlex import quote as shquote
from typing import Optional, Tuple
from ..errors import UserError
from ..remote import parse_remote_path


getuser = partial(input, "Username: ")


def register_parser(subparser):
    parser = subparser.add_parser("login", help = "Log into Nextstrain.org (and other remotes)")

    parser.add_argument(
        "remote",
        help    = cleandoc("""
            Remote URL to log in to, like the remote source/destination URLs
            used by the `nextstrain remote` family of commands.  Only the
            domain name (technically, the origin) of the URL is required/used,
            but a full URL may be specified.
            """),
        metavar = "<remote-url>",
        nargs   = "?",
        default = "nextstrain.org")

    parser.add_argument(
        "--username", "-u",
        metavar = "<name>",
        help    = "The username to log in as.  If not provided, the :envvar:`NEXTSTRAIN_USERNAME`"
                  " environment variable will be used if available, otherwise you'll be"
                  " prompted to enter your username.",
        default = environ.get("NEXTSTRAIN_USERNAME"))

    parser.add_argument(
        "--no-prompt",
        help    = "Never prompt for authentication (via web browser or username/password);"
                  " succeed only if there are login credentials in the environment or"
                  " existing valid/renewable tokens saved locally, otherwise error. "
                  " Useful for scripting.",
        action  = 'store_true')

    parser.add_argument(
        "--renew",
        help    = "Renew existing tokens, if possible. "
                  " Useful to refresh group membership information (for example) sooner"
                  " than the tokens would normally be renewed.",
        action  = "store_true")

    parser.epilog = cleandoc("""
        For automation purposes, you may opt to provide environment variables instead
        of interactive input and/or command-line options:

        .. envvar:: NEXTSTRAIN_USERNAME

            Username on nextstrain.org.  Ignored if :option:`--username` is also
            provided.

        .. envvar:: NEXTSTRAIN_PASSWORD

            Password for nextstrain.org user.  Required if :option:`--no-prompt` is
            used without existing valid/renewable tokens.

        If you want to suppress ever opening a web browser automatically, you
        may set the environment variable ``NOBROWSER=1``.
        """)

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote)
    assert url.origin

    if opts.renew:
        user = remote.renew(url.origin)
        if not user:
            raise UserError("Renewal failed or not possible.  Please login again.")
        return

    user = remote.current_user(url.origin)

    if not user:
        username = opts.username
        password = environ.get("NEXTSTRAIN_PASSWORD")

        if opts.no_prompt and (username is None or password is None):
            raise UserError(f"No {url.origin} credentials found and --no-prompt prevents interactive login.")

        print(f"Logging into {url.origin}…")
        print()

        # If we have either a username or a password, then obtain a complete
        # set of credentials and do password-based login.
        #
        # If we have neither, we'll do browser-based login.
        if username is not None or password is not None:
            credentials = lambda: prompt_for_credentials(username, password)
        else:
            credentials = None

        user = remote.login(url.origin, credentials)
        print()
    else:
        if opts.username is not None and opts.username != user.username:
            raise UserError(f"""
                Login requested for {opts.username}, but {user.username} is already logged in to {url.origin}.
                
                Please logout first if you want to switch users.
                """)

    print(f"Logged into {url.origin} as {user.username}.")
    print(f"Log out with `nextstrain logout {shquote(url.origin)}`.")


def prompt_for_credentials(username: Optional[str], password: Optional[str]) -> Tuple[str, str]:
    if username is not None:
        print(f"Username: {username}")
    else:
        username = prompt(getuser)

    if password is not None:
        print("Password: (from environment)")
    else:
        password = prompt(getpass)

    print()

    return username, password


def prompt(prompter):
    try:
        return prompter()
    except (EOFError, KeyboardInterrupt):
        print()
        raise UserError("Aborted by user input")

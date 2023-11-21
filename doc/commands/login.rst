.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain login

.. _nextstrain login:

================
nextstrain login
================

.. code-block:: none

    usage: nextstrain login [-h] [--username <name>] [--no-prompt] [--renew] [<remote-url>]


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

positional arguments
====================



.. option:: <remote-url>

    Remote URL to log in to, like the remote source/destination URLs
    used by the `nextstrain remote` family of commands.  Only the
    domain name (technically, the origin) of the URL is required/used,
    but a full URL may be specified.

options
=======



.. option:: -h, --help

    show this help message and exit

.. option:: --username <name>, -u <name>

    The username to log in as.  If not provided, the :envvar:`NEXTSTRAIN_USERNAME` environment variable will be used if available, otherwise you'll be prompted to enter your username.

.. option:: --no-prompt

    Never prompt for authentication (via web browser or username/password); succeed only if there are login credentials in the environment or existing valid/renewable tokens saved locally, otherwise error.  Useful for scripting.

.. option:: --renew

    Renew existing tokens, if possible.  Useful to refresh group membership information (for example) sooner than the tokens would normally be renewed.

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
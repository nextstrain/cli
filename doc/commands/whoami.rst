.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain whoami

.. _nextstrain whoami:

=================
nextstrain whoami
=================

.. code-block:: none

    usage: nextstrain whoami [-h] [<remote-url>]


Show information about the logged-in user for Nextstrain.org (and other
remotes).

The username, email address (if available), and Nextstrain Groups memberships
of the currently logged-in user are shown.

Exits with an error if no one is logged in.

positional arguments
====================



.. option:: <remote-url>

    Remote URL for which to show the logged-in user.  Expects URLs like
    the remote source/destination URLs used by the `nextstrain remote`
    family of commands.  Only the domain name (technically, the origin)
    of the URL is required/used, but a full URL may be specified.

options
=======



.. option:: -h, --help

    show this help message and exit


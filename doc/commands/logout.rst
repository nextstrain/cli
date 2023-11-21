.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain logout

.. _nextstrain logout:

=================
nextstrain logout
=================

.. code-block:: none

    usage: nextstrain logout [-h] [<remote-url>]


Log out of Nextstrain.org (and other remotes) by deleting locally-saved
credentials.

The authentication tokens are removed but not invalidated, so if you used them
outside of the `nextstrain` command, they will remain valid until they expire.

Other devices/clients (like your web browser) are not logged out of
Nextstrain.org (or other remotes).

positional arguments
====================



.. option:: <remote-url>

    Remote URL to log out of, like the remote source/destination URLs
    used by the `nextstrain remote` family of commands.  Only the
    domain name (technically, the origin) of the URL is required/used,
    but a full URL may be specified.

options
=======



.. option:: -h, --help

    show this help message and exit


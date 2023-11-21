.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain authorization

.. _nextstrain authorization:

========================
nextstrain authorization
========================

.. code-block:: none

    usage: nextstrain authorization [-h] [<remote-url>]


Produce an Authorization header appropriate for the web API of nextstrain.org
(and other remotes).

This is a development tool unnecessary for normal usage.  It's useful for
directly making API requests to nextstrain.org (and other remotes) with `curl`
or similar commands.  For example::

    curl -si https://nextstrain.org/whoami \
        --header "Accept: application/json" \
        --header @<(nextstrain authorization)

Exits with an error if no one is logged in.

positional arguments
====================



.. option:: <remote-url>

    Remote URL for which to produce an Authorization header.  Expects
    URLs like the remote source/destination URLs used by the
    `nextstrain remote` family of commands.  Only the domain name
    (technically, the origin) of the URL is required/used, but a full
    URL may be specified.

options
=======



.. option:: -h, --help

    show this help message and exit


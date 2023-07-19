.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain authorization

.. _nextstrain authorization:

========================
nextstrain authorization
========================

.. code-block:: none

    usage: nextstrain authorization [-h]


Produce an Authorization header appropriate for nextstrain.org's web API.

This is a development tool unnecessary for normal usage.  It's useful for
directly making API requests to nextstrain.org with `curl` or similar
commands.  For example::

    curl -si https://nextstrain.org/whoami \
        --header "Accept: application/json" \
        --header @<(nextstrain authorization)

Exits with an error if no one is logged in.

options
=======



.. option:: -h, --help

    show this help message and exit


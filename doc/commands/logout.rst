.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain logout

.. _nextstrain logout:

=================
nextstrain logout
=================

.. code-block:: none

    usage: nextstrain logout [-h]


Log out of Nextstrain.org by deleting locally-saved credentials.

The authentication tokens are removed but not invalidated, so if you used them
outside of the `nextstrain` command, they will remain valid until they expire.

Other devices/clients (like your web browser) are not logged out of
Nextstrain.org.

options
=======



.. option:: -h, --help

    show this help message and exit


.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain update

.. _nextstrain update:

=================
nextstrain update
=================

.. code-block:: none

    usage: nextstrain update [-h] [<runtime>]


Updates a Nextstrain runtime to the latest available version, if any.

The default runtime (docker) is updated when this command is run
without arguments.  Provide a runtime name as an argument to update a specific
runtime instead.

Three runtimes currently support updates: Docker, Conda, and Singularity.
Updates may take several minutes as new software versions are downloaded.

This command also checks for newer versions of the Nextstrain CLI (the
`nextstrain` program) itself and will suggest upgrade instructions if an
upgrade is available.

positional arguments
====================



.. option:: <runtime>

    The Nextstrain runtime to check. One of {docker, conda, singularity, ambient, aws-batch}. (default: docker)

optional arguments
==================



.. option:: -h, --help

    show this help message and exit


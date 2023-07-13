.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain setup

.. _nextstrain setup:

================
nextstrain setup
================

.. code-block:: none

    usage: nextstrain setup [-h] [--dry-run] [--force] [--set-default] <runtime>


Sets up a Nextstrain runtime for use with `nextstrain build`, `nextstrain
view`, etc.

Only the Conda runtime currently supports automated set up, but this command
may still be used with other runtimes to check an existing (manual) setup and
set the runtime as the default on success.

Exits with an error code if automated set up fails or if setup checks fail.

positional arguments
====================



.. option:: <runtime>

    The Nextstrain runtime to set up. One of {docker, conda, singularity, ambient, aws-batch}.

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

.. option:: --dry-run

    Don't actually set up anything, just show what would happen.

.. option:: --force

    Ignore existing setup, if any, and always start fresh.

.. option:: --set-default

    Use the runtime as the default if set up is successful.


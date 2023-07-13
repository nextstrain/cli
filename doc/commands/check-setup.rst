.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain check-setup

.. _nextstrain check-setup:

======================
nextstrain check-setup
======================

.. code-block:: none

    usage: nextstrain check-setup [-h] [--set-default] [<runtime> [<runtime> ...]]


Checks for supported runtimes.

Five runtimes are tested by default:

  • Our Docker image is the preferred runtime.  Docker itself must
    be installed and configured on your computer first, but once it is, the
    runtime is robust and reproducible.

  • Our Conda runtime will be tested for existence and appearance of
    completeness. This runtime is more isolated and reproducible than your
    ambient runtime, but is less isolated and robust than the Docker
    runtime.

  • Our Singularity runtime uses the same container image as our Docker
    runtime.  Singularity must be installed and configured on your computer
    first, although it is often already present on HPC systems.  This runtime
    is more isolated and reproducible than the Conda runtime, but potentially
    less so than the Docker runtime.

  • Your ambient setup will be tested for snakemake, augur, and auspice.
    Their presence implies a working runtime, but does not guarantee
    it.

  • Remote jobs on AWS Batch.  Your AWS account, if credentials are available
    in your environment or via aws-cli configuration, will be tested for the
    presence of appropriate resources.  Their presence implies a working AWS
    Batch runtime, but does not guarantee it.

Provide one or more runtime names as arguments to test just those instead.

Exits with an error code if the default runtime (docker) is not
supported or, when the default runtime is omitted from checks, if none of the
checked runtimes are supported.

positional arguments
====================



.. option:: <runtime>

    The Nextstrain runtimes to check. (default: docker, conda, singularity, ambient, aws-batch)

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

.. option:: --set-default

    Set the default runtime to the first which passes check-setup. Checks run in the order given, if any, otherwise in the default order: docker, conda, singularity, ambient, aws-batch.


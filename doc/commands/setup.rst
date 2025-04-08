.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain setup

.. _nextstrain setup:

================
nextstrain setup
================

.. code-block:: none

    usage: nextstrain setup [--dry-run] [--force] [--set-default] <pathogen-name>[@<version>[=<url>]]
           nextstrain setup [--dry-run] [--force] [--set-default] <runtime-name>
           nextstrain setup --help


Sets up a Nextstrain pathogen for use with `nextstrain run` or a Nextstrain
runtime for use with `nextstrain run`, `nextstrain build`, `nextstrain view`,
etc.

For pathogens, set up involves downloading a specific version of the pathogen's
Nextstrain workflows.  By convention, this download is from Nextstrain's
repositories.  More than one version of the same pathogen may be set up and
used independently.  This can be useful for comparing analyses across workflow
versions.  A default version can be set.

For runtimes, only the Conda runtime currently supports fully-automated set up,
but this command may still be used with other runtimes to check an existing
(manual) setup and set the runtime as the default on success.

Exits with an error code if automated set up fails or if setup checks fail.

positional arguments
====================



.. option:: <pathogen>|<runtime>

    The Nextstrain pathogen or runtime to set up.

    A pathogen is usually the plain name of a Nextstrain-maintained
    pathogen (e.g. ``measles``), optionally with an ``@<version>``
    specifier (e.g. ``measles@v42``).  If ``<version>`` is specified in
    this case, it must be a tag name (i.e. a release name), development
    branch name, or a development commit id.

    A pathogen may also be fully-specified as ``<name>@<version>=<url>``
    where ``<name>`` and ``<version>`` in this case are (mostly)
    arbitrary and ``<url>`` points to a ZIP file containing the
    pathogen repository contents (e.g.
    ``https://github.com/nextstrain/measles/zipball/83b446d67fc03de2ce1c72bb1345b4c4eace7231``).

    A runtime is one of {docker, conda, singularity, ambient, aws-batch}.


options
=======



.. option:: -h, --help

    show this help message and exit

.. option:: --dry-run

    Don't actually set up anything, just show what would happen.

.. option:: --force

    Ignore existing setup, if any, and always start fresh.

.. option:: --set-default

    Use this pathogen version or runtime as the default if set up is successful.


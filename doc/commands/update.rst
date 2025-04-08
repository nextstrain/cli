.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain update

.. _nextstrain update:

=================
nextstrain update
=================

.. code-block:: none

    usage: nextstrain update [<pathogen-name>[@<version>] | <runtime-name> […]]
           nextstrain update
           nextstrain update --help


Updates Nextstrain pathogens and runtimes to the latest available versions, if any.

When this command is run without arguments, the default version for each set up
pathogen (none) and the default runtime (docker)
are updated.  Provide one or more pathogens and/or runtimes as arguments to
update a select list instead.

Three runtimes currently support updates: Docker, Conda, and Singularity.
Updates may take several minutes as new software versions are downloaded.

This command also checks for newer versions of the Nextstrain CLI (the
`nextstrain` program) itself and will suggest upgrade instructions if an
upgrade is available.

positional arguments
====================



.. option:: <pathogen>|<runtime>

    The Nextstrain pathogens and/or runtimes to update.

    A pathogen is the name (and optionally, version) of a previously
    set up pathogen.  See :command-reference:`nextstrain setup`.  If no
    version is specified, then the default version will be updated to
    the latest available version.

    A runtime is one of {docker, conda, singularity, ambient, aws-batch}.




options
=======



.. option:: -h, --help

    show this help message and exit


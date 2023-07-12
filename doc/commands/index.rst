:orphan:

.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain

.. _nextstrain:

==========
nextstrain
==========

.. code-block:: none

    usage: nextstrain [-h] {build,view,deploy,remote,shell,update,setup,check-setup,login,logout,whoami,version,init-shell,authorization,debugger} ...


Nextstrain command-line interface (CLI)

The `nextstrain` program and its subcommands aim to provide a consistent way to
run and visualize pathogen builds and access Nextstrain components like Augur
and Auspice across computing platforms such as Docker, Conda, and AWS Batch.

Run `nextstrain <command> --help` for usage information about each command.
See <:doc:`/index`> for more documentation.

optional arguments
==================



.. option:: -h, --help

    show this help message and exit

commands
========



.. option:: build

    Run pathogen build. See :doc:`/commands/build`.

.. option:: view

    View pathogen builds and narratives. See :doc:`/commands/view`.

.. option:: deploy

    Deploy pathogen build. See :doc:`/commands/deploy`.

.. option:: remote

    Upload, download, and manage remote datasets and narratives.. See :doc:`/commands/remote/index`.

.. option:: shell

    Start a new shell in a runtime. See :doc:`/commands/shell`.

.. option:: update

    Update a runtime. See :doc:`/commands/update`.

.. option:: setup

    Set up a runtime. See :doc:`/commands/setup`.

.. option:: check-setup

    Check runtime setups. See :doc:`/commands/check-setup`.

.. option:: login

    Log into Nextstrain.org. See :doc:`/commands/login`.

.. option:: logout

    Log out of Nextstrain.org. See :doc:`/commands/logout`.

.. option:: whoami

    Show information about the logged-in user. See :doc:`/commands/whoami`.

.. option:: version

    Show version information. See :doc:`/commands/version`.

.. option:: init-shell

    Print shell init script. See :doc:`/commands/init-shell`.

.. option:: authorization

    Print an HTTP Authorization header. See :doc:`/commands/authorization`.

.. option:: debugger

    Start a debugger. See :doc:`/commands/debugger`.


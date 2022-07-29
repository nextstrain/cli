=========
Upgrading
=========

This page describes how to upgrade the Nextstrain CLI--the ``nextstrain``
command--itself, without also upgrading the entire Nextstrain
:term:`docs:runtime`.

The way to upgrade depends on what kind of Nextstrain CLI installation you have
(i.e. how it was first installed), so running ``nextstrain check-setup``:

.. code-block:: console
    :emphasize-lines: 10

    $ nextstrain check-setup
    A new version of nextstrain-cli, X.Y.Z, is available!  You're running A.B.C.

    See what's new in the changelog:

        https://github.com/nextstrain/cli/blob/X.Y.Z/CHANGES.md#readme

    Upgrade by running:

        [UPGRADE COMMAND]

    Testing your setup…
    …

will suggest a command to run to upgrade ``nextstrain``, if there are any
upgrades available.  Run the suggested command to perform the upgrade.

Afterwards, you can check that the new version was installed by running:

.. code-block:: console

    $ nextstrain version
    nextstrain.cli X.Y.Z

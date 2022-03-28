=========
Upgrading
=========

This page describes how to upgrade the Nextstrain CLI--the ``nextstrain``
command--itself, without also upgrading the entire Nextstrain
:term:`docs:runtime`.

The first step is to figure out what kind of Nextstrain CLI installation you
have.

If you run ``conda activate nextstrain`` before running ``nextstrain``
commands, then you're using a **Conda-based installation** like we describe in
the Nextstrain :doc:`installation steps <docs:install>`.  In this case, run the
following to upgrade:

.. code-block:: bash

    conda activate nextstrain
    mamba update -c conda-forge -c bioconda nextstrain-cli

Otherwise, you're using another installation method and running:

.. code-block:: console
    :emphasize-lines: 6

    $ nextstrain check-setup
    A new version of nextstrain-cli, X.Y.Z, is available!  You're running A.B.C.

    Upgrade by running:

        [UPGRADE COMMAND]

    Testing your setup…
    …

will suggest a command to run to upgrade ``nextstrain``.  Run the suggested
command to perform the upgrade.

Either way, you can check the new version that was installed by running:

.. code-block:: console

    $ nextstrain version
    nextstrain.cli 3.2.1

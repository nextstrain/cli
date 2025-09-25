=========
Upgrading
=========

This page describes how to upgrade the Nextstrain CLI--the ``nextstrain``
command--itself, which is separate from updating the Nextstrain :term:`runtime`
in which :term:`pathogen` workflows are run.  Though they're managed
separately, both the Nextstrain CLI itself and runtimes may be updated using
the :doc:`/commands/update` command.

The quickest way to upgrade Nextstrain CLI itself is by running ``nextstrain
update cli``:

.. code-block:: console

    $ nextstrain update cli
    Updating Nextstrain CLI…
    A new version of Nextstrain CLI, X.Y.Z, is available!  You're running A.B.C.

    See what's new in the changelog:

        https://docs.nextstrain.org/projects/cli/en/X.Y.Z/changes/

    Running `curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | DESTINATION=/home/you/.nextstrain/cli-standalone bash -s X.Y.Z` via bash
    --> Temporary working directory: /tmp/tmp.ID4f0HWZVf
    --> Downloading https://nextstrain.org/cli/download/X.Y.Z/standalone-x86_64-unknown-linux-gnu.tar.gz
    
    […]

    Updated Nextstrain CLI!

    All updates successful!

This command automates the upgrade steps, which depend on the kind of
Nextstrain CLI installation you have (i.e. how it was first installed).

Afterwards, you can check that the new version was installed by running:

.. code-block:: console

    $ nextstrain version
    Nextstrain CLI X.Y.Z

While we work hard to make updates nondisruptive and ensure new versions of
Nextstrain CLI remain backwards compatible, it's still important to read the
changelog entries between your current version and the latest version.  The
changelog exists to help you understand changes you may need to make to your
usage of Nextstrain CLI and help you learn about new features you may want to
use or bug fixes you may want to have.

Running ``nextstrain check-setup`` first will let you check for a new version
of Nextstrain CLI, read the changelog, and preview the update command that will
be run by ``nextstrain update cli``.

.. code-block:: console
    :emphasize-lines: 4-8, 16

    $ nextstrain check-setup
    […]

    A new version of Nextstrain CLI, X.Y.Z, is available!  You're running A.B.C.

    See what's new in the changelog:

        https://docs.nextstrain.org/projects/cli/en/X.Y.Z/changes/

    Update your standalone installation of Nextstrain CLI automatically by running:

        nextstrain update cli

    or manually by running:

        curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | DESTINATION=/home/you/.nextstrain/cli-standalone bash -s X.Y.Z

    or by downloading a new archive from:

        https://nextstrain.org/cli/download/X.Y.Z/standalone-x86_64-unknown-linux-gnu.tar.gz

If you wish, you may run the suggested command yourself (e.g. ``curl …``) to
perform the upgrade instead of using ``nextstrain update cli``.

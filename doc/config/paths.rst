===================
Paths configuration
===================

Nextstrain CLI uses various local filesystem paths for config and runtime data.
If necessary, the defaults can be overridden by environment variables.

.. envvar:: NEXTSTRAIN_HOME

    Directory for config and other application data.  Used as the basis for all
    other paths.

    Default is :file:`~/.nextstrain/`, assuming a home directory is
    discernable.  If not, :file:`.nextstrain` (i.e. in the current directory)
    is used as a last resort.

.. envvar:: NEXTSTRAIN_CONFIG

    File for :doc:`configuration </config/file>`.

    Default is :file:`{${NEXTSTRAIN_HOME}}/config`.

.. envvar:: NEXTSTRAIN_SECRETS

    File for secrets (e.g. nextstrain.org tokens) managed by
    :doc:`/commands/login` and :doc:`/commands/logout`.

    Default is :file:`{${NEXTSTRAIN_HOME}}/secrets`.

.. envvar:: NEXTSTRAIN_LOCK

    File for serializing access to other config files to prevent corruption and
    other bugs.

    Default is :file:`{${NEXTSTRAIN_HOME}}/lock`.

.. envvar:: NEXTSTRAIN_PATHOGENS

    Directory for pathogen workflow data managed by :doc:`/commands/setup`,
    e.g. local copies of pathogen repos like `nextstrain/measles
    <https://github.com/nextstrain/measles>`__.

    Default is :file:`{${NEXTSTRAIN_HOME}}/pathogens/`.

.. envvar:: NEXTSTRAIN_RUNTIMES

    Directory for runtime-specific data, e.g. Singularity images or a Conda
    environment.  Each runtime uses a subdirectory within here.

    Default is :file:`{${NEXTSTRAIN_HOME}}/runtimes/`.

.. envvar:: NEXTSTRAIN_SHELL_HISTORY

    File for preserving command history across :doc:`/commands/shell` invocations.

    Default is :file:`{${NEXTSTRAIN_HOME}}/shell-history`.

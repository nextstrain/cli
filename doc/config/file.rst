===========
Config file
===========

Nextstrain CLI uses an INI-style configuration file to store information about
the runtimes that are set up.  For example:

.. code-block:: ini

    [core]
    runner = docker

    [docker]
    image = nextstrain/base:build-20230623T174208Z

The default configuration file is :file:`~/.nextstrain/config`.  This path may
be overridden entirely by the :envvar:`NEXTSTRAIN_CONFIG` environment variable.
Alternatively, the path of the containing directory (i.e.
:file:`~/.nextstrain/`) may be overridden by the :envvar:`NEXTSTRAIN_HOME`
environment variable.


Sections
========

- `Core variables`_
- :ref:`Docker runtime variables <docker-config>`
- :ref:`Singularity runtime variables <singularity-config>`
- :ref:`AWS Batch runtime variables <aws-batch-config>`


Core variables
==============

.. glossary::

    :index:`core.runner <configuration variable; core.runner>`
        Short name of the default :term:`runtime`.  Typically set by running
        one of:

        .. code-block:: none

            nextstrain setup --set-default <runtime>
            nextstrain check-setup --set-default

        If not set, the :doc:`/runtimes/docker` (``docker``) is used.

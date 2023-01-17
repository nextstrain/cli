========
Glossary
========

Terms used by Nextstrain CLI.  Primarily intended for developers new to the
codebase, though some terms are also used in user-facing messages and
documentation.

.. glossary::

    computing environment
        A general term for any given set of software, configuration, and other
        resources available for running programs.  Computing environments are
        often nested, with inner environments inheriting to varying degrees
        from the outer environments.  The isolation and reproducibility of
        different computing environments varies widely.

        :term:`Nextstrain runtimes <runtime>` are examples of specific
        computing environments.

    computing platform
        The foundation of a :term:`computing environment` (or part of it), such
        as Docker, Conda, AWS Batch, etc.

    runner
        The code (i.e. Python module, e.g. :file:`nextstrain/cli/runner/docker.py`)
        which arranges to execute things inside a :term:`runtime`.

        Used by commands like ``nextstrain build`` and ``nextstrain view``, for
        example, to execute ``snakemake`` or ``auspice`` (respectively).

        Runners have a 1:1 mapping to runtimes.

    runtime
        A specific :term:`computing environment` (e.g. container image or Conda
        environment) in which Nextstrain CLI expects to find and execute other
        Nextstrain programs.

        Current runtimes:

          - Docker with the `nextstrain/base image <https://hub.docker.com/r/nextstrain/base>`_
          - Conda with the `nextstrain-base meta-package <https://anaconda.org/nextstrain/nextstrain-base>`__
          - Ambient
          - AWS Batch with the `nextstrain/base image`_
  
        Each runtime provides specific versions of Nextstrain's software
        components, like Augur and Auspice.

        Runtimes are managed (maintained, tested, versioned, released) by the
        Nextstrain team, except for the ambient runtime.  The ambient runtime
        is special in that it's whatever computing environment in which
        Nextstrain CLI itself is running (i.e. managed by the user).

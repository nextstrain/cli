============
Installation
============

.. hint::
   This is a reference page with brief pointers for installing and setting up
   Nextstrain CLI. For a more comprehensive installation guide, please see `our
   general Nextstrain installation page
   <https://docs.nextstrain.org/page/install.html>`__.

The ``nextstrain`` command
==========================

Install the ``nextstrain`` command with one of the installation methods below.

Standalone
----------

Use our installers to quickly install a self-contained ("standalone") version
of Nextstrain CLI on Linux:

.. code-block:: bash

    curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | bash

macOS:

.. code-block:: bash

    curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/mac | bash

or Windows:

.. code-block:: powershell

    Invoke-RestMethod https://nextstrain.org/cli/installer/windows | Invoke-Expression

Follow the instructions from the installer at the end.


From PyPI
---------

.. note::
    Nextstrain CLI is written in Python 3 and requires at least Python 3.6.  There
    are many ways to install Python 3 on Windows, macOS, or Linux, including the
    `official packages`_, `Homebrew`_ for macOS, and the `Anaconda Distribution`_.
    Details are beyond the scope of this guide, but make sure you install Python
    3.6 or higher. You may already have Python 3 installed, especially if you're on
    Linux. Check by running ``python --version`` or ``python3 --version``.

    .. _official packages: https://www.python.org/downloads/
    .. _Homebrew: https://brew.sh
    .. _Anaconda Distribution: https://www.anaconda.com/distribution/

Use `Pip <https://pip.pypa.io>`__ to install the `nextstrain-cli package on
PyPI <https://pypi.org/project/nextstrain-cli>`__:

.. code-block:: console

   $ python3 -m pip install nextstrain-cli
   Collecting nextstrain-cli
   […a lot of output…]
   Successfully installed nextstrain-cli-6.0.2

This package also works great with `Pipx
<https://pipxproject.github.io/pipx/>`__, a nice alternative to Pip for
command-line apps like this one:

.. code-block:: console

   $ pipx install nextstrain-cli
   Installing to directory '/home/tom/.local/pipx/venvs/nextstrain-cli'
     installed package nextstrain-cli 6.0.2, Python 3.6.9
     These apps are now globally available
       - nextstrain
   done! ✨ 🌟 ✨


From Bioconda
-------------

Use `Conda <https://conda.io>`__ (or `Mamba <https://mamba.readthedocs.io>`__) to
install the `nextstrain-cli package in Bioconda
<https://bioconda.github.io/recipes/nextstrain-cli/README.html>`__:

.. code-block:: bash

    conda install nextstrain-cli \
      -c conda-forge -c bioconda \
      --strict-channel-priority \
      --override-channels

Checking the version
--------------------

Whatever installation method you choose, make sure the ``nextstrain`` command
is available after installation by running ``nextstrain version``:

.. code-block:: console

   $ nextstrain version
   nextstrain.cli 6.0.2

The version you get will probably be different than the one shown in the
example above.


Runtimes
========

.. XXX TODO: Move this heading and subheadings (with modification) to their own
   top-level doc section (e.g. like Remotes).
     -trs, 12 Jan 2023

The Nextstrain CLI provides a consistent interface and computing environment
for running and visualizing Nextstrain pathogen builds across several different
computing platforms, such as `Docker <https://docker.com>`__, `Conda
<https://docs.conda.io/en/latest/miniconda.html>`__,
:ref:`Singularity <installation/singularity>`, and `AWS Batch
<https://aws.amazon.com/batch/>`__.

We call the provided computing environments the :term:`Nextstrain runtimes
<docs:runtime>`.  Each runtime provides specific versions of Nextstrain's
software components, like `Augur <https://github.com/nextstrain/augur>`__ and
`Auspice <https://github.com/nextstrain/auspice>`__.

At least one of these runtimes must be setup in order for many of
``nextstrain``'s subcommands to work, such as ``nextstrain build`` and
``nextstrain view``.

The default runtime is Docker, using the `nextstrain/base`_ container image.
Containers provide a tremendous amount of benefit for scientific workflows by
isolating dependencies and increasing reproducibility. However, they're not
always appropriate, so a Conda runtime, Singularity runtime, and "ambient"
runtime are also supported.  The installation and setup of supported runtimes
is described below.

.. _nextstrain/base: https://github.com/nextstrain/docker-base

Docker
------

`Docker <https://docker.com>`__ is a very popular container system
freely-available for all platforms. When you use Docker with the Nextstrain
CLI, you don't need to install any other Nextstrain software dependencies as
validated versions are already bundled into a container image by the Nextstrain
team.

On macOS, download and install `Docker Desktop`_, also known previously as
"Docker for Mac".

On Linux, install Docker with the standard package manager. For example, on
Ubuntu, you can install Docker with ``sudo apt install docker.io``.

On Windows, install `Docker Desktop`_ with its support for a WSL2 backend.

Once you've installed Docker, proceed with :ref:`checking your setup
<installation/check-setup>`.

.. _Docker Desktop: https://www.docker.com/products/docker-desktop

Conda
-----

`Conda <https://docs.conda.io/en/latest/miniconda.html>`__ is a very popular
packaging system freely-available for all platforms. When you use Nextstrain
CLI's built-in Conda support, you don't need to install any other Nextstrain
software dependencies yourself as they're automatically managed in an isolated
location (isolated even from other Conda environments you may manage yourself).

On macOS and Linux, run ``nextstrain setup conda`` to get started.

This runtime is not directly supported on Windows, but you can use `WSL2
<https://docs.microsoft.com/en-us/windows/wsl/wsl2-index>`__ to "switch" to
Linux and run the above setup command.

.. _installation/singularity:

Singularity
-----------

Singularity is a container system freely-available for Linux platforms.  It is
commonly available on institutional HPC systems as an alternative to Docker,
which is often not supported on such systems.  When you use Singularity with
the Nextstrain CLI, you don't need to install any other Nextstrain software
dependencies as validated versions are already bundled into a container image
by the Nextstrain team.

Run ``nextstrain setup singularity`` to get started.

Note that the Singularity project forked into two separate projects in late
2021: `SingularityCE`_ under `Sylabs`_ and `Apptainer`_ under the `Linux
Foundation`_.  Either fork should work with Nextstrain CLI, as both projects
still provide very similar interfaces and functionality via the ``singularity``
command.  You can read `Sylab's announcement`_ and `Apptainer's announcement`_
for more information on the fork.

.. _SingularityCE: https://sylabs.io/singularity/
.. _Sylabs: https://sylabs.io/
.. _Apptainer: https://apptainer.org
.. _Linux Foundation: https://www.linuxfoundation.org/
.. _Sylab's announcement: https://sylabs.io/2022/06/singularityce-is-singularity/
.. _Apptainer's announcement: https://apptainer.org/news/community-announcement-20211130

Ambient
-------

The "ambient" runtime allows you to use the Nextstrain CLI with your own ambient
setup, for when you cannot or do not want to have Nextstrain CLI manage its own
runtime.

However, you will need to make sure all of the Nextstrain software dependencies
are available locally or "ambiently" on your computer. A common way to do this
is by manually using `Conda <https://docs.conda.io/en/latest/miniconda.html>`__
to manage your own environment that includes the required software, however
you're responsible for making sure the correct software is installed and kept
up-to-date. It is also possible to install the required Nextstrain software
`Augur <https://github.com/nextstrain/augur>`__ and `Auspice
<https://github.com/nextstrain/auspice>`__ and their dependencies manually,
although this is not recommended.

Once you've installed dependencies, proceed with :ref:`checking your setup
<installation/check-setup>`.

AWS Batch
---------

`AWS Batch <https://aws.amazon.com/batch/>`__ is an advanced computing
platform which allows you to launch and monitor Nextstrain builds in the
cloud from the comfort of your own computer. The same image used by the local
Docker runtime is used by AWS Batch, making your builds more reproducible, and
builds have access to computers with very large CPU and memory allocations if
necessary.

The initial setup is quite a bit more involved, but :doc:`detailed instructions
<aws-batch>` are available.

Once you've setup AWS, proceed with :ref:`checking your setup
<installation/check-setup>`.

.. _installation/check-setup:

Checking your setup
===================

After installation and setup, run ``nextstrain check-setup --set-default`` to
ensure everything works and automatically pick an appropriate default runtime
based on what's available. You should see output similar to the following:

.. code-block:: console

   $ nextstrain check-setup --set-default
   nextstrain-cli is up to date!

   Testing your setup…

   # docker is supported
   ✔ yes: docker is installed
   ✔ yes: docker run works
   ✔ yes: containers have access to >2 GiB of memory
   ✔ yes: image is new enough for this CLI version

   # conda is supported
   ✔ yes: operating system is supported
   ✔ yes: runtime data dir doesn't have spaces
   ✔ yes: snakemake is installed and runnable
   ✔ yes: augur is installed and runnable
   ✔ yes: auspice is installed and runnable

   # singularity is supported
   ✔ yes: singularity is installed
   ✔ yes: singularity works

   # ambient is not supported
   ✔ yes: snakemake is installed and runnable
   ✘ no: augur is installed and runnable
   ✘ no: auspice is installed and runnable

   # aws-batch is not supported
   ✘ no: job description "nextstrain-job" exists
   ✘ no: job queue "nextstrain-job-queue" exists
   ✘ no: S3 bucket "nextstrain-jobs" exists

   All good!  Supported Nextstrain runtimes: docker, conda, singularity

   Setting default runtime to docker.

If the output doesn't say "All good!" and list at least one supported
Nextstrain runtime (typically Docker, Conda, Singularity, or ambient), then
something may be wrong with your installation.

The default is written to the :file:`~/.nextstrain/config` file. If multiple
runtimes are supported, you can override the default for specific runs
using command-line options such as ``--docker``, ``--conda``,
``--singularity``, ``--ambient``, and ``--aws-batch``, e.g. ``nextstrain build
--ambient …``.

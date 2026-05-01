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
    Nextstrain CLI is written in Python 3 and requires at least Python 3.10.  There
    are many ways to install Python 3 on Windows, macOS, or Linux, including the
    `official packages`_, `Homebrew`_ for macOS, and the `Anaconda Distribution`_.
    Details are beyond the scope of this guide, but make sure you install Python
    3.10 or higher. You may already have Python 3 installed, especially if you're on
    Linux. Check by running ``python --version`` or ``python3 --version``.

    .. _official packages: https://www.python.org/downloads/
    .. _Homebrew: https://brew.sh
    .. _Anaconda Distribution: https://www.anaconda.com/download

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

Install the `nextstrain-cli package from Bioconda
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


A Nextstrain runtime
====================

If you intend to run commands like :doc:`/commands/build` and
:doc:`/commands/view`, then you'll need to set up at least one :term:`runtime`.
See the :doc:`runtimes overview </runtimes/index>` for a comparison of the
options and brief set up instructions for each.  Runtime set up typically
concludes by running:

.. code-block:: bash

    nextstrain setup <runtime>


.. _installation/check-setup:

Checking your setup
===================

After installation and runtime set up, run ``nextstrain check-setup
--set-default`` to ensure everything works and automatically pick an
appropriate default runtime based on what's available. You should see output
similar to the following:

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

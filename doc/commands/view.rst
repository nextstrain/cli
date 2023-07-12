.. default-role:: literal

.. program:: nextstrain view

===============
nextstrain view
===============

.. code-block:: none

    usage: nextstrain view [options] <path>
           nextstrain view --help


Visualizes a completed pathogen builds or narratives in Auspice, the Nextstrain
visualization app.

<path> may be a `dataset (.json) file`_ or `narrative (.md) file`_ to start
Auspice and directly open the specified dataset or narrative in a browser.
Adjacent datasets and/or narratives may also be viewable as an appropriate data
directory for Auspice is automatically inferred from the file path.

<path> may also be a directory with one of the following layouts::

    <path>/
    ├── auspice/
    │   └── *.json
    └── narratives/
        └── *.md

    <path>/
    ├── auspice/
    │   └── *.json
    └── *.md

    <path>/
    ├── *.json
    └── narratives/
        └── *.md

    <path>/
    ├── *.json
    └── *.md

Dataset and narrative files will be served, respectively, from **auspice**
and/or **narratives** subdirectories under the given <path> if the
subdirectories exist.  Otherwise, files will be served from the given directory
<path> itself.

If your pathogen build directory follows our conventional layout by containing
an **auspice** directory (and optionally a **narratives** directory), then you
can give ``nextstrain view`` the same path as you do ``nextstrain build``.

Note that by convention files named **README.md** or **group-overview.md** will
be ignored for the purposes of finding available narratives.

.. _dataset (.json) file: https://docs.nextstrain.org/page/reference/glossary.html#term-dataset
.. _narrative (.md) file: https://docs.nextstrain.org/page/reference/glossary.html#term-narrative

positional arguments
====================



.. option:: <path>

    Path to a directory containing dataset JSON and/or narrative Markdown files for Auspice, or a directory containing an auspice/ and/or narratives/ directory, or a specific dataset JSON or narrative Markdown file.

optional arguments
==================



.. option:: --help, -h

    Show a brief help message of common options and exit

.. option:: --help-all

    Show a full help message of all options and exit

.. option:: --open

    Open a web browser automatically (the default)

.. option:: --no-open

    Do not open a web browser automatically 

.. option:: --allow-remote-access

    Allow other computers on the network to access the website (alias for --host=0.0.0.0)

.. option:: --host <ip/hostname>

    Listen on the given hostname or IP address instead of the default 127.0.0.1

.. option:: --port <number>

    Listen on the given port instead of the default port 4000

runtime selection options
=========================

Select the Nextstrain runtime to use, if the
default is not suitable.

.. option:: --docker

    Run commands inside a container image using Docker. (default)

.. option:: --ambient

    Run commands in the ambient environment, outside of any container image.

.. option:: --conda

    Run commands with access to a fully-managed Conda environment.

.. option:: --singularity

    Run commands inside a container image using Singularity.

runtime options
===============

Options shared by all runtimes.

.. option:: --env <name>[=<value>]

    Set the environment variable <name> to the value in the current environment (i.e. pass it thru) or to the given <value>. May be specified more than once. Overrides any variables of the same name set via --envdir. When this option or --envdir is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. The "well-known" variables are AUGUR_RECURSION_LIMIT, AUGUR_MINIFY_JSON, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, ID3C_URL, ID3C_USERNAME, ID3C_PASSWORD, RETHINK_HOST, and RETHINK_AUTH_KEY. Pass those variables explicitly via --env or --envdir if you need them in combination with other variables. 

.. option:: --envdir <path>

    Set environment variables from the envdir at <path>. May be specified more than once. An envdir is a directory containing files describing environment variables. Each filename is used as the variable name. The first line of the contents of each file is used as the variable value. When this option or --env is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. See the description of --env for more details. 

development options
===================

These should generally be unnecessary unless you're developing Nextstrain.

.. option:: --image <image>

    Container image name to use for the Nextstrain runtime (default: nextstrain/base for Docker and AWS Batch, docker://nextstrain/base for Singularity)

.. option:: --exec <prog>

    Program to run inside the runtime

development options for --docker
================================



.. option:: --augur <dir>

    Replace the image's copy of augur with a local copy

.. option:: --auspice <dir>

    Replace the image's copy of auspice with a local copy

.. option:: --fauna <dir>

    Replace the image's copy of fauna with a local copy

.. option:: --sacra <dir>

    Replace the image's copy of sacra with a local copy

.. option:: --docker-arg ...

    Additional arguments to pass to `docker run`


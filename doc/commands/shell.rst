.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain shell

.. _nextstrain shell:

================
nextstrain shell
================

.. code-block:: none

    usage: nextstrain shell [options] <directory> [...]
           nextstrain shell --help


Start a new shell inside a Nextstrain runtime to run ad-hoc
commands and perform debugging.

positional arguments
====================



.. option:: <directory>

    Path to pathogen build directory

.. option:: ...

    Additional arguments to pass to the executed program

options
=======



.. option:: --help, -h

    Show a brief help message of common options and exit

.. option:: --help-all

    Show a full help message of all options and exit

runtime selection options
=========================

Select the Nextstrain runtime to use, if the
default is not suitable.

.. option:: --docker

    Run commands inside a container image using Docker. (default)

.. option:: --conda

    Run commands with access to a fully-managed Conda environment.

.. option:: --singularity

    Run commands inside a container image using Singularity.

runtime options
===============

Options shared by all runtimes.

.. option:: --env <name>[=<value>]

    Set the environment variable ``<name>`` to the value in the current environment (i.e. pass it thru) or to the given ``<value>``. May be specified more than once. Overrides any variables of the same name set via :option:`--envdir`. When this option or :option:`--envdir` is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. The "well-known" variables are ``AUGUR_RECURSION_LIMIT``, ``AUGUR_MINIFY_JSON``, ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_SESSION_TOKEN``, ``ID3C_URL``, ``ID3C_USERNAME``, ``ID3C_PASSWORD``, ``RETHINK_HOST``, and ``RETHINK_AUTH_KEY``. Pass those variables explicitly via :option:`--env` or :option:`--envdir` if you need them in combination with other variables. 

.. option:: --envdir <path>

    Set environment variables from the envdir at ``<path>``. May be specified more than once. An envdir is a directory containing files describing environment variables. Each filename is used as the variable name. The first line of the contents of each file is used as the variable value. When this option or :option:`--env` is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. Envdirs may also be specified by setting ``NEXTSTRAIN_RUNTIME_ENVDIRS`` in the environment to a ``:``-separated list of paths. See the description of :option:`--env` for more details. 

development options
===================

These should generally be unnecessary unless you're developing Nextstrain.

.. option:: --image <image>

    Container image name to use for the Nextstrain runtime (default: nextstrain/base for Docker and AWS Batch, docker://nextstrain/base for Singularity)

.. option:: --augur <dir>

    Replace the image's copy of augur with a local copy

.. option:: --auspice <dir>

    Replace the image's copy of auspice with a local copy

.. option:: --fauna <dir>

    Replace the image's copy of fauna with a local copy

.. option:: --exec <prog>

    Program to run inside the runtime

development options for --docker
================================



.. option:: --docker-arg ...

    Additional arguments to pass to `docker run`


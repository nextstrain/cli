.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain build

.. _nextstrain build:

================
nextstrain build
================

.. code-block:: none

    usage: nextstrain build [options] <directory> [...]
           nextstrain build --help


Runs a pathogen build in a Nextstrain runtime.

The build directory should contain a Snakefile, which will be run with
snakemake.

You need at least one runtime available to run a build.  You can test if the
Docker, Conda, ambient, or AWS Batch runtimes are properly supported on your
computer by running::

    nextstrain check-setup

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from provisioning a runtime environment, so that running builds
is as easy as possible.  It also lets us more seamlessly make runtime
changes in the future as desired or necessary.

positional arguments
====================



.. option:: <directory>

    Path to pathogen build directory.  Required, except when the AWS Batch runtime is in use and --attach and either --no-download or --cancel are given.  

.. option:: ...

    Additional arguments to pass to the executed program

options
=======



.. option:: --help, -h

    Show a brief help message of common options and exit

.. option:: --help-all

    Show a full help message of all options and exit

.. option:: --detach

    Run the build in the background, detached from your terminal.  Re-attach later using :option:`--attach`.  Currently only supported when also using :option:`--aws-batch`.

.. option:: --detach-on-interrupt

    Detach from the build when an interrupt (e.g. :kbd:`Control-C` or ``SIGINT``) is received.  Interrupts normally cancel the build (when sent twice if stdin is a terminal, once otherwise).  Currently only supported when also using :option:`--aws-batch`.

.. option:: --attach <job-id>

    Re-attach to a :option:`--detach`'ed build to view output and download results.  Currently only supported when also using :option:`--aws-batch`.

.. option:: --cancel

    Immediately cancel (interrupt/stop) the :option:`--attach`'ed build.  Currently only supported when also using :option:`--aws-batch`.

.. option:: --cpus <count>

    Number of CPUs/cores/threads/jobs to utilize at once.  Limits containerized (Docker, AWS Batch) builds to this amount.  Informs Snakemake's resource scheduler when applicable.  Informs the AWS Batch instance size selection.  By default, no constraints are placed on how many CPUs are used by a build; builds may use all that are available if they're able to.

.. option:: --memory <quantity>

    Amount of memory to make available to the build.  Units of b, kb, mb, gb, kib, mib, gib are supported.  Limits containerized (Docker, AWS Batch) builds to this amount.  Informs Snakemake's resource scheduler when applicable.  Informs the AWS Batch instance size selection.  

.. option:: --download <pattern>

    Only download new or modified files matching ``<pattern>`` from the
    remote build.  Shell-style advanced globbing is supported, but be
    sure to escape wildcards or quote the whole pattern so your shell
    doesn't expand them.  May be passed more than once.  Currently only
    supported when also using :option:`--aws-batch`.  Default is to
    download every new or modified file.

    Besides basic glob features like single-part wildcards (``*``),
    character classes (``[…]``), and brace expansion (``{…, …}``),
    several advanced globbing features are also supported: multi-part
    wildcards (``**``), extended globbing (``@(…)``, ``+(…)``, etc.),
    and negation (``!…``).




.. option:: --no-download

    Do not download any files from the remote build when it completes. Currently only supported when also using :option:`--aws-batch`.

.. option:: --no-logs

    Do not show the log messages of the remote build. Currently only supported when also using :option:`--aws-batch`. Default is to show all log messages, even when attaching to a completed build.

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

.. option:: --ambient

    Run commands in the ambient environment, outside of any container image or managed environment.

.. option:: --aws-batch

    Run commands remotely on AWS Batch inside the Nextstrain container image.

runtime options
===============

Options shared by all runtimes.

.. option:: --env <name>[=<value>]

    Set the environment variable ``<name>`` to the value in the current environment (i.e. pass it thru) or to the given ``<value>``. May be specified more than once. Overrides any variables of the same name set via :option:`--envdir`. When this option or :option:`--envdir` is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. The "well-known" variables are ``AUGUR_RECURSION_LIMIT``, ``AUGUR_MINIFY_JSON``, ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_SESSION_TOKEN``, ``ID3C_URL``, ``ID3C_USERNAME``, ``ID3C_PASSWORD``, ``RETHINK_HOST``, and ``RETHINK_AUTH_KEY``. Pass those variables explicitly via :option:`--env` or :option:`--envdir` if you need them in combination with other variables. 

.. option:: --envdir <path>

    Set environment variables from the envdir at ``<path>``. May be specified more than once. An envdir is a directory containing files describing environment variables. Each filename is used as the variable name. The first line of the contents of each file is used as the variable value. When this option or :option:`--env` is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. See the description of :option:`--env` for more details. 

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

development options for --aws-batch
===================================

See <https://docs.nextstrain.org/projects/cli/page/aws-batch>
for more information.

.. option:: --aws-batch-job <name>

    Name of the AWS Batch job definition to use

.. option:: --aws-batch-queue <name>

    Name of the AWS Batch job queue to use

.. option:: --aws-batch-s3-bucket <name>

    Name of the AWS S3 bucket to use as shared storage

.. option:: --aws-batch-cpus <count>

    Number of vCPUs to request for job

.. option:: --aws-batch-memory <mebibytes>

    Amount of memory in MiB to request for job


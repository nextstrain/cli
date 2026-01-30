.. default-role:: literal

.. role:: command-reference(ref)

.. program:: nextstrain run

.. _nextstrain run:

==============
nextstrain run
==============

.. code-block:: none

    usage: nextstrain run [options] <pathogen-name>[@<version>]|<pathogen-path> <workflow-name> <analysis-directory> [<target> [<target> [...]]]
           nextstrain run --help


Runs a pathogen workflow in a Nextstrain runtime with config and input from an
analysis directory and outputs written to that same directory.

This command focuses on the routine running of existing pathogen workflows
(mainly provided by Nextstrain) using your own configuration, data, and other
supported customizations.  Pathogens are initially set up using `nextstrain
setup` and can be updated over time as desired using `nextstrain update`.
Multiple versions of a pathogen may be set up and run independently without
conflict, allowing for comparisons of output across versions.  The same
pathogen workflow may also be concurrently run multiple times with separate
analysis directories (i.e. different configs, input data, etc.) without
conflict, allowing for independent outputs and analyses.

Compared to `nextstrain build`, this command is a higher-level interface to
running pathogen workflows that does not require knowledge of Git or management
of pathogen repositories and source code.  For now, the `nextstrain build`
command remains more suitable for active authorship and development of
workflows.

All Nextstrain runtimes are supported.  For AWS Batch, all runs will detach
after submission and `nextstrain build` must be used to further monitor or
manage the run and download results after completion.

positional arguments
====================



.. option:: <pathogen-name>[@<version>]|<pathogen-path>

    The name (and optionally, version) of a previously set up pathogen.
    See :command-reference:`nextstrain setup`.  If no version is
    specified, then the default version (if any) will be used.

    Alternatively, the local path to a directory that is a pathogen
    repository.  For this case to be recognized as such, the path must
    contain a separator (/) or consist entirely of the current
    directory (.) or parent directory (..) specifier.

    Required.

.. option:: <workflow-name>

    The name of a workflow for the given pathogen, e.g. typically
    ``ingest``, ``phylogenetic``, or ``nextclade``.

    Available workflows may vary per pathogen (and possibly between
    pathogen version).  Some pathogens may provide multiple variants or
    base configurations of a top-level workflow, e.g. as in
    ``phylogenetic/mpxv`` and ``phylogenetic/hmpxv1``.
    Run ``nextstrain version --pathogens`` to see a list of registered
    workflows per pathogen version. If the pathogen does not have
    registered workflows, then refer to the pathogen's own documentation
    for valid workflow names.

    Workflow names conventionally correspond directly to directory
    paths in the pathogen source, but this may not always be the case:
    the pathogen's registration info can provide an explicit path for a
    workflow name.

    Required.

.. option:: <analysis-directory>

    The path to your analysis directory.  The workflow uses this as its
    working directory for all local inputs and outputs, including
    config files, input data files, resulting output data files, log
    files, etc.

    We recommend keeping your config files and static input files (e.g.
    reference sequences, inclusion/exclusion lists, annotations, etc.)
    in a version control system, such as Git, so you can keep track of
    changes over time and recover previous versions.  When using
    version control, dynamic inputs (e.g. downloaded input filefs) and
    outputs (e.g. resulting data files, log files, etc.) should
    generally be marked as ignored/excluded from tracking, such as via
    :file:`.gitignore` for Git.

    An empty directory will be automatically created if the given path
    does not exist but its parent directory does.

    Required.

.. option:: <target>

    One or more workflow targets.  A target is either a file path
    (relative to :option:`<analysis-directory>`) produced by the
    workflow or the name of a workflow rule or step.

    Available targets will vary per pathogen (and between versions of
    pathogens).  Refer to the pathogen's own documentation for valid
    targets.

    Optional.

options
=======



.. option:: --force

    Force a rerun of the whole workflow even if everything seems up-to-date.

.. option:: --cpus <count>

    Number of CPUs/cores/threads/jobs to utilize at once.  Limits containerized (Docker, AWS Batch) workflow runs to this amount.  Informs Snakemake's resource scheduler when applicable.  Informs the AWS Batch instance size selection.  By default, no constraints are placed on how many CPUs are used by a workflow run; workflow runs may use all that are available if they're able to.

.. option:: --memory <quantity>

    Amount of memory to make available to the workflow run.  Units of b, kb, mb, gb, kib, mib, gib are supported.  Limits containerized (Docker, AWS Batch) workflow runs to this amount.  Informs Snakemake's resource scheduler when applicable.  Informs the AWS Batch instance size selection.  

.. option:: --exclude-from-upload <pattern>

    Exclude files matching ``<pattern>`` from being uploaded as part of
    the remote build.  Shell-style advanced globbing is supported, but
    be sure to escape wildcards or quote the whole pattern so your
    shell doesn't expand them.  May be passed more than once.
    Currently only supported when also using :option:`--aws-batch`.
    Default is to upload the entire pathogen build directory (except
    for some ancillary files which are always excluded).

    Note that files excluded from upload may still be downloaded from
    the remote build, e.g. if they're created by it, and if downloaded
    will overwrite the local files.  When attaching to the build, use
    :option:`nextstrain build --no-download` to avoid downloading any
    files or :option:`nextstrain build --exclude-from-download` to
    avoid downloading specific files.

    Besides basic glob features like single-part wildcards (``*``),
    character classes (``[…]``), and brace expansion (``{…, …}``),
    several advanced globbing features are also supported: multi-part
    wildcards (``**``), extended globbing (``@(…)``, ``+(…)``, etc.),
    and negation (``!…``).

    Patterns should be relative to the build directory.




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

.. option:: --ambient

    Run commands in the ambient environment, outside of any container image or managed environment.

.. option:: --aws-batch

    Run commands remotely on AWS Batch inside the Nextstrain container image.

runtime options
===============

Options shared by all runtimes.

.. option:: --env <name>[=<value>]

    Set the environment variable ``<name>`` to the value in the current environment (i.e. pass it thru) or to the given ``<value>``. May be specified more than once. Overrides any variables of the same name set via :option:`--envdir`. When this option or :option:`--envdir` is given, the default behaviour of automatically passing thru several "well-known" variables is disabled. The "well-known" variables are ``AUGUR_SEARCH_PATHS``, ``AUGUR_RECURSION_LIMIT``, ``AUGUR_MINIFY_JSON``, ``AUGUR_DEBUG``, ``AUGUR_PROFILE``, ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_SESSION_TOKEN``, ``ID3C_URL``, ``ID3C_USERNAME``, ``ID3C_PASSWORD``, ``RETHINK_HOST``, and ``RETHINK_AUTH_KEY``. Pass those variables explicitly via :option:`--env` or :option:`--envdir` if you need them in combination with other variables. 

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

development options for --aws-batch
===================================

See <https://docs.nextstrain.org/projects/cli/page/aws-batch>
for more information.

.. option:: --aws-batch-job <name>

    Name of the AWS Batch job definition to use

.. option:: --aws-batch-queue <name>

    Name of the AWS Batch job queue to use

.. option:: --aws-batch-s3-bucket [s3://]<name>[/<prefix>]

    Name (or URL) of the AWS S3 bucket to use as shared storage, with optional prefix for keys

.. option:: --aws-batch-cpus <count>

    Number of vCPUs to request for job

.. option:: --aws-batch-memory <mebibytes>

    Amount of memory in MiB to request for job


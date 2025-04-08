"""
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
"""

from inspect import cleandoc
from shlex import quote as shquote
from textwrap import dedent
from .. import runner
from ..argparse import add_extended_help_flags, MkDirectoryPath, SKIP_AUTO_DEFAULT_IN_HELP
from ..debug import DEBUGGING
from ..errors import UserError
from ..pathogens import PathogenVersion
from ..runner import aws_batch, docker, singularity
from ..util import byte_quantity, split_image_name
from ..volume import NamedVolume
from . import build


def register_parser(subparser):
    """
    %(prog)s [options] <pathogen-name>[@<version>] <workflow-name> <analysis-directory> [<target> [<target> [...]]]
    %(prog)s --help
    """

    parser = subparser.add_parser("run", help = "Run pathogen workflow", add_help = False)

    # Positional parameters
    parser.add_argument(
        "pathogen",
        metavar = "<pathogen-name>[@<version>]",
        help    = cleandoc(f"""
            The name (and optionally, version) of a previously set up pathogen.
            See :command-reference:`nextstrain setup`.  If no version is
            specified, then the default version (if any) will be used.

            Required.
            """))

    parser.add_argument(
        "workflow",
        metavar = "<workflow-name>",
        help    = cleandoc(f"""
            The name of a workflow for the given pathogen, e.g. typically
            ``ingest``, ``phylogenetic``, or ``nextclade``.

            Available workflows may vary per pathogen (and possibly between
            pathogen version).  Some pathogens may provide multiple variants or
            base configurations of a top-level workflow, e.g. as in
            ``phylogenetic/mpxv`` and ``phylogenetic/hmpxv1``.  Refer to the
            pathogen's own documentation for valid workflow names.

            Workflow names conventionally correspond directly to directory
            paths in the pathogen source, but this may not always be the case.

            Required.
            """))

    parser.add_argument(
        "analysis_directory",
        metavar = "<analysis-directory>",
        type    = MkDirectoryPath(),
        help    = cleandoc("""
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
            """))

    parser.add_argument(
        "targets",
        metavar = "<target>",
        nargs   = "*",
        help    = cleandoc("""
            One or more workflow targets.  A target is either a file path
            (relative to :option:`<analysis-directory>`) produced by the
            workflow or the name of a workflow rule or step.

            Available targets will vary per pathogen (and between versions of
            pathogens).  Refer to the pathogen's own documentation for valid
            targets.

            Optional.
            """))

    parser.add_argument(
        "--force",
        help    = "Force a rerun of the whole workflow even if everything seems up-to-date.",
        action  = "store_true")

    # XXX TODO: Consider if and how to share argument definitions with `build`?
    # Starting with copying for now, but the expectation is they should be
    # aligned as much as possible (at least where they overlap).
    #  -trs, 1 Nov 2024

    parser.add_argument(
        "--cpus",
        help    = "Number of CPUs/cores/threads/jobs to utilize at once.  "
                  "Limits containerized (Docker, AWS Batch) workflow runs to this amount.  "
                  "Informs Snakemake's resource scheduler when applicable.  "
                  "Informs the AWS Batch instance size selection.  "
                  "By default, no constraints are placed on how many CPUs are used by a workflow run; "
                  "workflow runs may use all that are available if they're able to.",
        metavar = "<count>",
        type    = int)

    parser.add_argument(
        "--memory",
        help    = "Amount of memory to make available to the workflow run.  "
                  "Units of b, kb, mb, gb, kib, mib, gib are supported.  "
                  "Limits containerized (Docker, AWS Batch) workflow runs to this amount.  "
                  "Informs Snakemake's resource scheduler when applicable.  "
                  "Informs the AWS Batch instance size selection.  ",
        metavar = "<quantity>",
        type    = byte_quantity)

    # XXX TODO: AWS Batch support for `nextstrain run`.  Include options like
    # --detach, --detach-on-interrupt, --attach, --cancel, etc?  For now, only
    # support detached Batch builds and kick the can to `build` for further
    # monitoring/management.  Maybe we leave it that way?
    #   -trs, 1 Nov 2024 & 28 Feb 2025

    parser.add_argument(
        "--exclude-from-upload",
        metavar = "<pattern>",
        help    = dedent(f"""\
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
            character classes (``[…]``), and brace expansion (``{{…, …}}``),
            several advanced globbing features are also supported: multi-part
            wildcards (``**``), extended globbing (``@(…)``, ``+(…)``, etc.),
            and negation (``!…``).

            Patterns should be relative to the build directory.

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        action  = "append")

    # Support --help and --help-all
    add_extended_help_flags(parser)

    # Register runner flags and arguments
    #
    # Note that we intentionally do not pass "..." (Ellipsis) as an element in
    # "exec" because this `nextstrain run` command, unlike `nextstrain build`,
    # is intended to fully encapsulate the details of Snakemake's invocation in
    # order to present a simplified, stable interface.
    #   -trs, 6 Feb 2025
    runner.register_runners(
        parser,
        exec = ["snakemake"]) # Other default exec args defined below

    return parser


def run(opts):
    build.assert_overlay_volumes_support(opts)

    # Assert AWS Batch support; this command requires overlays.
    if opts.__runner__ is aws_batch and not docker.image_supports(docker.IMAGE_FEATURE.aws_batch_overlays, opts.image):
        raise UserError(f"""
            The Nextstrain runtime image version in use

                {opts.image}

            is too old to support `nextstrain run` with AWS Batch.

            Please update the runtime image to at least version

                {split_image_name(opts.image)[0]}:{docker.IMAGE_FEATURE.aws_batch_overlays.value}

            using `nextstrain update docker`.  Alternatively, use a runtime
            other than AWS Batch.
            """)

    # Resolve pathogen and workflow names to a local workflow directory.
    pathogen = PathogenVersion(opts.pathogen)

    workflow_directory = pathogen.workflow_path(opts.workflow)

    if not workflow_directory.is_dir() or not (workflow_directory / "Snakefile").is_file():
        raise UserError(f"""
            No {opts.workflow!r} workflow for pathogen {opts.pathogen!r} found {f"in {str(workflow_directory)!r}" if DEBUGGING else "locally"}.

            Maybe you need to update to a newer version of the pathogen?

            Hint: to update the pathogen, run `nextstrain update {shquote(pathogen.name)}`.
            """)

    # The pathogen volume is the pathogen directory (i.e. repo).
    # The workflow volume is the workflow directory within the pathogen directory.
    # The build volume is the user's analysis directory and will be the working directory.
    pathogen_volume, workflow_volume = build.pathogen_volumes(workflow_directory, name = "pathogen")
    build_volume = NamedVolume("build", opts.analysis_directory)

    # for containerized runtimes (e.g. Docker, Singularity, and AWS Batch)
    opts.volumes.append(pathogen_volume)
    opts.volumes.append(build_volume)

    print(f"Running the {opts.workflow!r} workflow for pathogen {pathogen}")

    # Set up Snakemake invocation.
    opts.default_exec_args += [
        # Useful to see what's going on; see also 08ffc925.
        "--printshellcmds",

        # In our experience,¹ it's rarely useful to fail on incomplete outputs
        # (Snakemake's default behaviour) instead of automatically regenerating
        # them.
        #
        # ¹ <https://discussion.nextstrain.org/t/snakemake-throwing-incompletefilesexception-when-using-forceall/1397/4>
        "--rerun-incomplete",

        # Pin down rerun triggers so they don't drift over time as Snakemake
        # changes the defaults.  In the past, changes to this have been
        # confusing/caused errors.
        "--rerun-triggers", "code", "input", "mtime", "params", "software-env",

        *(["--forceall"]
            if opts.force else []),

        # Workdir will be the analysis volume (/nextstrain/build in a
        # containerized runtime), so explicitly point to the Snakefile.
        "--snakefile=%s/Snakefile" % (
            docker.mount_point(workflow_volume)
                if opts.__runner__ in {docker, singularity, aws_batch} else
            workflow_volume.src.resolve(strict = True)),

        # Pass thru appropriate resource options.
        #
        # Snakemake requires the --cores option as of 5.11, so provide a
        # default to insulate our users from this and make Nextstrain builds
        # fast-by-default.  For more rationale/details, see a similar comment
        # in nextstrain/cli/command/build.py.
        #   -trs, 1 Nov 2024
        "--cores=%s" % (opts.cpus or "all"),

        # Named MB but is really MiB, so convert our count of bytes to MiB
        *(["--resources=mem_mb=%d" % (opts.memory // 1024**2)]
            if opts.memory else []),

        "--",

        *opts.targets,
    ]

    # XXX TODO: AWS Batch support for `nextstrain run`.  For now, only support
    # detached Batch builds and kick the can to `build` for further
    # monitoring/management.  In the future, maybe we'll support the full set
    # of AWS Batch options (see related comment in register_parser() above).
    #   -trs, 28 Feb 2025
    if opts.__runner__ is aws_batch:
        opts.detach = True
        opts.attach = None
        opts.cancel = None

    return runner.run(opts, working_volume = build_volume, cpus = opts.cpus, memory = opts.memory)

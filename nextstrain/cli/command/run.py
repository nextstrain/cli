# XXX FIXME command doc
"""
TKTKTK
"""

from shlex import quote as shquote
from .. import runner
from ..argparse import add_extended_help_flags, DirectoryPath
from ..debug import DEBUGGING
from ..errors import UserError
from ..paths import WORKFLOWS
from ..runner import ambient, conda, docker, singularity
from ..util import byte_quantity
from ..volume import NamedVolume
from . import build


def register_parser(subparser):
    """
    %(prog)s [options] <pathogen-name> <workflow-name> <analysis-directory> [<target> [<target> [...]]]
    %(prog)s --help
    """

    parser = subparser.add_parser("run", help = "Run pathogen workflow", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    # XXX TODO: consider if and how to share argument definitions with `build`
    # XXX TODO: options for --aws-batch, e.g. --detach, --detach-on-interrupt, --attach, --cancel, etc.
    # *OR* maybe only support detached Batch builds and kick the can to `build` for further monitoring/management?

    parser.add_argument(
        "--force",
        help    = "Force a rerun of the whole workflow even if everything seems up-to-date.",
        action  = "store_true")

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

    # Positional parameters
    parser.add_argument(
        "pathogen",
        help    = "Pathogen name.  Required.", # XXX FIXME: add details
        metavar = "<pathogen-name>")

    parser.add_argument(
        "workflow",
        help    = "Workflow name.  Required.", # XXX FIXME: add details
        metavar = "<workflow-name>")

    parser.add_argument(
        "analysis_directory",
        help    = "Analysis directory.  Required.", # XXX FIXME: add details
        type    = DirectoryPath,
        metavar = "<analysis-directory>")

    parser.add_argument(
        "targets",
        help    = "Output target; a file path produced by the workflow or the name of a workflow rule.  Optional.", # XXX FIXME: add details
        metavar = "<target>",
        nargs   = "*")

    # Register runner flags and arguments
    # XXX TODO: explain why an Ellipsis (...) is intentionally omitted
    runner.register_runners(
        parser,
        runners = [docker, ambient, conda, singularity], # XXX FIXME: aws_batch
        exec = ["snakemake"]) # Other default exec args defined below

    return parser


def run(opts):
    build.assert_overlay_volumes_support(opts)

    # Resolve pathogen and workflow names to a local workflow directory.
    # XXX FIXME: refactor into nextstrain/cli/workflow/…?
    # XXX FIXME: support versioned resolution, e.g. <pathogen-name>@<version>
    pathogen_directory = WORKFLOWS / opts.pathogen.lower()
    workflow_directory = pathogen_directory / opts.workflow.lower()

    # XXX FIXME: setup/update support
    if not pathogen_directory.is_dir():
        raise UserError(f"""
            No pathogen named {opts.pathogen!r} found {f"in {str(pathogen_directory)!r}" if DEBUGGING else "locally"}.

            Did you set it up?

            Hint: to set it up, run `nextstrain setup {shquote(opts.pathogen)}`.
            """)

    if not workflow_directory.is_dir():
        raise UserError(f"""
            No {opts.workflow!r} workflow for pathogen {opts.pathogen!r} found {f"in {str(workflow_directory)!r}" if DEBUGGING else "locally"}.

            Maybe you need to update to a newer version of the pathogen?

            Hint: to update the pathogen, run `nextstrain update {shquote(opts.pathogen)}`.
            """)

    # The build volume is the pathogen directory (i.e. repo).
    # The working volume is the workflow directory within the pathogen directory.
    # The analysis volume is the user's analysis directory and will be Snakemake's workdir.
    build_volume, working_volume = build.pathogen_volumes(workflow_directory)
    analysis_volume = NamedVolume("analysis", opts.analysis_directory)

    # for Docker, Singularity, and AWS Batch
    opts.volumes.append(build_volume)
    opts.volumes.append(analysis_volume)

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

        # XXX FIXME: explain
        "--rerun-triggers", "code", "input", "mtime", "params", "software-env",

        # XXX FIXME: explain
        *(["--forceall"]
            if opts.force else []),

        # Set workdir to the analysis volume.
        # XXX FIXME: aws_batch
        "--directory=%s" % (
            docker.mount_point(analysis_volume)
                if opts.__runner__ in {docker, singularity} else
            analysis_volume.src.resolve(strict = True)),

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

    return runner.run(opts, working_volume = working_volume, cpus = opts.cpus, memory = opts.memory)

"""
Runs a pathogen build in a Nextstrain runtime.

The build directory should contain a Snakefile, which will be run with
snakemake.

You need at least one runtime available to run a build.  You can test if the
Docker, Conda, ambient, or AWS Batch runtimes are properly supported on your
computer by running:

    nextstrain check-setup

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from provisioning a runtime environment, so that running builds
is as easy as possible.  It also lets us more seamlessly make runtime
changes in the future as desired or necessary.
"""

import re
from textwrap import dedent
from .. import runner
from ..argparse import add_extended_help_flags, AppendOverwriteDefault, SKIP_AUTO_DEFAULT_IN_HELP
from ..util import byte_quantity, warn
from ..volume import store_volume


def register_parser(subparser):
    """
    %(prog)s [options] <directory> [...]
    %(prog)s --help
    """

    parser = subparser.add_parser("build", help = "Run pathogen build", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    parser.add_argument(
        "--detach",
        help   = "Run the build in the background, detached from your terminal.  "
                 "Re-attach later using --attach.  "
                 "Currently only supported when also using --aws-batch.",
        action = "store_true")

    parser.add_argument(
        "--attach",
        help = "Re-attach to a --detach'ed build to view output and download results.  "
               "Currently only supported when also using --aws-batch.",
        metavar = "<job-id>")

    parser.add_argument(
        "--cpus",
        help    = "Number of CPUs/cores/threads/jobs to utilize at once.  "
                  "Limits containerized (Docker, AWS Batch) builds to this amount.  "
                  "Informs Snakemake's resource scheduler when applicable.  "
                  "Informs the AWS Batch instance size selection.  "
                  "By default, no constraints are placed on how many CPUs are used by a build; "
                  "builds may use all that are available if they're able to.",
        metavar = "<count>",
        type    = int)

    parser.add_argument(
        "--memory",
        help    = "Amount of memory to make available to the build.  "
                  "Units of b, kb, mb, gb, kib, mib, gib are supported.  "
                  "Limits containerized (Docker, AWS Batch) builds to this amount.  "
                  "Informs Snakemake's resource scheduler when applicable.  "
                  "Informs the AWS Batch instance size selection.  ",
        metavar = "<quantity>",
        type    = byte_quantity)

    parser.add_argument(
        "--download",
        metavar = "<pattern>",
        help    = dedent(f"""\
            Only download new or modified files matching <pattern> from the
            remote build.  Shell-style advanced globbing is supported, but be
            sure to escape wildcards or quote the whole pattern so your shell
            doesn't expand them.  May be passed more than once.  Currently only
            supported when also using --aws-batch.  Default is to download
            every new or modified file.

            Besides basic glob features like single-part wildcards (*),
            character classes ([…]), and brace expansion ({{…, …}}), several
            advanced globbing features are also supported: multi-part wildcards
            (**), extended globbing (@(…), +(…), etc.), and negation (!…).

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        default = True,
        action  = AppendOverwriteDefault)

    parser.add_argument(
        "--no-download",
        help   = "Do not download any files from the remote build when it completes. "
                 "Currently only supported when also using --aws-batch."
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        dest   = "download",
        action = "store_false")

    # A --logs option doesn't make much sense right now for most of our
    # runtimes, but I can see how it might in the future.  So we're ready if
    # that future comes to pass, set up --no-logs as if there's a --logs option
    # enabled by default.  This also avoids a double negative in conditions,
    # e.g. avoids writing "if not opts.no_logs".
    #   -trs, 9 Feb 2023
    parser.set_defaults(logs = True)
    parser.add_argument(
        "--no-logs",
        help   = "Do not show the log messages of the remote build. "
                 "Currently only supported when also using --aws-batch. "
                 "Default is to show all log messages, even when attaching to a completed build."
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        dest   = "logs",
        action = "store_false")

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        action  = store_volume("build"))

    # Register runner flags and arguments
    runner.register_runners(parser, exec = ["snakemake", "--printshellcmds", ...])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    # Automatically pass thru appropriate resource options to Snakemake to
    # avoid the user having to repeat themselves (once for us, once for
    # snakemake).
    if opts.exec == "snakemake":
        snakemake_opts = parse_snakemake_args(opts.extra_exec_args)

        if not snakemake_opts["--cores"]:
            if opts.cpus:
                opts.extra_exec_args += ["--cores=%d" % opts.cpus]
            else:
                # Snakemake requires the --cores option as of 5.11, so provide
                # a default to insulate our users from this and make Nextstrain
                # builds fast-by-default.  See the message of the commit which
                # introduced this line for more details.
                #   -trs, 25 May 2022
                opts.extra_exec_args += ["--cores=all"]
        else:
            if opts.cpus:
                warn(dedent("""
                    Warning: The explicit %s option passed to Snakemake prevents
                    the Nextstrain CLI from automatically providing one based on its
                    --cpus option.  This may or may not be what you expect.
                    """ % (snakemake_opts["--cores"][0],)))

        if opts.memory:
            if not snakemake_opts["--resources"]:
                # Named MB but is really MiB, so convert our count of bytes to MiB
                opts.extra_exec_args += ["--resources=mem_mb=%d" % (opts.memory // 1024**2)]
            else:
                # XXX TODO: Support parsing of --resources to see if "mem_mb" is
                # provided.  If it's not, we could add our own "mem_mb" constraint
                # alongside the other values of --resources.  Punting on this
                # because it's not as simple as appending an additional argument.
                # So for now, if folks are specifying their own --resources,
                # they'll also need to explicitly provide "mem_mb", which may mean
                # repeating a previous --memory argument they provided us.
                #   -trs, 20 May 2020
                #
                # We might accomplish this TODO with a bit of a trick: using a
                # stack-walking --log-handler-script to get access to
                # Snakemake's in-process state and update --resources from
                # there.  I wrote a proof of concept¹ when exploring options
                # around custom resources for an ncov PR², and it worked well
                # in manual testing.
                #   -trs, 1 Feb 2023
                #
                # ¹ <https://gist.github.com/tsibley/6b3b5c37e651518d85810945a4140cde>
                # ² <https://github.com/nextstrain/ncov/pull/1045>
                warn(dedent("""
                    Warning: The explicit %s option passed to Snakemake prevents
                    the Nextstrain CLI from automatically providing a "mem_mb" resource
                    based on its --memory option.  This may or may not be what you expect.
                    """ % (snakemake_opts["--resources"][0],)))

    return runner.run(opts, working_volume = opts.build, cpus = opts.cpus, memory = opts.memory)


def parse_snakemake_args(args):
    """
    Inspects a tiny subset of Snakemake's CLI arguments in order to determine
    their presence or absence in our invocation.

    >>> sorted(parse_snakemake_args(["--cores"]).items())
    [('--cores', ['--cores']), ('--resources', [])]

    >>> sorted(parse_snakemake_args(["--resources=mem_mb=100"]).items())
    [('--cores', []), ('--resources', ['--resources'])]

    >>> sorted(parse_snakemake_args(["-j", "8", "--res", "mem_mb=100"]).items())
    [('--cores', ['-j']), ('--resources', ['--res'])]

    >>> sorted(parse_snakemake_args(["-j8"]).items())
    [('--cores', ['-j']), ('--resources', [])]

    >>> sorted(parse_snakemake_args([]).items())
    [('--cores', []), ('--resources', [])]
    """
    # XXX TODO: Consider using a small ArgumentParser() for this in the
    # future, when we can require Python 3.7 and use parse_intermixed_args().
    #   -trs, 20 May 2020

    opts = {
        "-j" if re.search(r"^-j\d+$", arg) else arg
            for arg in map(lambda arg: arg.split("=", 1)[0], args)
    }

    # These prefix lists statically embed the unambiguous option prefixes
    # accepted as of Snakemake 5.17.0.
    cores = {
        "--cores", # documented
        "--core",
        "--cor",
        "--jobs", # documented
        "-j", # documented
    }

    resources = {
        "--resources", # documented
        "--resource",
        "--resourc",
        "--resour",
        "--resou",
        "--reso",
        "--res", # documented
    }

    return {
        "--cores": list(cores & opts),
        "--resources": list(resources & opts),
    }

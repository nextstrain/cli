"""
Runs a pathogen build in a Nextstrain runtime.

The build directory should contain a Snakefile, which will be run with
snakemake.

You need at least one runtime available to run a build.  You can test if the
Docker, Conda, Singularity, ambient, or AWS Batch runtimes are properly
supported on your computer by running::

    nextstrain check-setup

The `nextstrain build` command is designed to cleanly separate the Nextstrain
build interface from provisioning a runtime environment, so that running builds
is as easy as possible.  It also lets us more seamlessly make runtime
changes in the future as desired or necessary.
"""

import re
from pathlib import Path, PurePosixPath
from textwrap import dedent
from typing import Tuple
from .. import runner
from ..argparse import add_extended_help_flags, AppendOverwriteDefault, SKIP_AUTO_DEFAULT_IN_HELP
from ..debug import debug
from ..errors import UsageError, UserError
from ..runner import docker, singularity, aws_batch
from ..util import byte_quantity, runner_name, split_image_name, warn
from ..volume import NamedVolume


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
                 "Re-attach later using :option:`--attach`.  "
                 "Currently only supported when also using :option:`--aws-batch`.",
        action = "store_true")

    parser.add_argument(
        "--detach-on-interrupt",
        help   = "Detach from the build when an interrupt (e.g. :kbd:`Control-C` or ``SIGINT``) is received.  "
                 "Interrupts normally cancel the build (when sent twice if stdin is a terminal, once otherwise).  "
                 "Currently only supported when also using :option:`--aws-batch`.",
        action = "store_true")

    parser.add_argument(
        "--attach",
        help = "Re-attach to a :option:`--detach`'ed build to view output and download results.  "
               "Currently only supported when also using :option:`--aws-batch`.",
        metavar = "<job-id>")

    parser.add_argument(
        "--cancel",
        help = "Immediately cancel (interrupt/stop) the :option:`--attach`'ed build.  "
               "Currently only supported when also using :option:`--aws-batch`.",
        action = "store_true")

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
            Only download new or modified files matching ``<pattern>`` from the
            remote build.  Shell-style advanced globbing is supported, but be
            sure to escape wildcards or quote the whole pattern so your shell
            doesn't expand them.  May be passed more than once.  Currently only
            supported when also using :option:`--aws-batch`.  Default is to
            download every new or modified file.

            Besides basic glob features like single-part wildcards (``*``),
            character classes (``[…]``), and brace expansion (``{{…, …}}``),
            several advanced globbing features are also supported: multi-part
            wildcards (``**``), extended globbing (``@(…)``, ``+(…)``, etc.),
            and negation (``!…``).

            Patterns should be relative to the build directory.

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        default = True,
        action  = AppendOverwriteDefault)

    parser.add_argument(
        "--no-download",
        help   = "Do not download any files from the remote build when it completes. "
                 "Currently only supported when also using :option:`--aws-batch`."
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        dest   = "download",
        action = "store_false")

    parser.add_argument(
        "--exclude-from-download",
        metavar = "<pattern>",
        help    = dedent(f"""\
            Exclude files matching ``<pattern>`` from being downloaded from
            the remote build.  Equivalent to passing a negated pattern to
            :option:`--download`.  That is, the following are equivalent::

                --exclude-from-download 'xyz'
                --download '!xyz'

            Refer to :option:`--download` for usage details, but note that this
            option doesn't support already-negated patterns (e.g. ``!…`` or
            ``!(…)``).

            This option exists to parallel :option:`--exclude-from-upload`.

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        dest    = "download",
        type    = lambda pattern: f"!{pattern}",
        action  = AppendOverwriteDefault)

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
            will overwrite the local files.  Use :option:`--no-download` to
            avoid downloading any files, or :option:`--exclude-from-download`
            to avoid downloading specific files, e.g.::

                --exclude-from-upload 'results/**' \\
                --exclude-from-download 'results/**'

            Your shell's brace expansion can also be used to shorten this, e.g.::

                --exclude-from-{{up,down}}load='results/**'

            Besides basic glob features like single-part wildcards (``*``),
            character classes (``[…]``), and brace expansion (``{{…, …}}``),
            several advanced globbing features are also supported: multi-part
            wildcards (``**``), extended globbing (``@(…)``, ``+(…)``, etc.),
            and negation (``!…``).

            Patterns should be relative to the build directory.

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        action  = "append")

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
                 "Currently only supported when also using :option:`--aws-batch`. "
                 "Default is to show all log messages, even when attaching to a completed build."
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        dest   = "logs",
        action = "store_false")

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory.  "
                  "Required, except when the AWS Batch runtime is in use and :option:`--attach` and either :option:`--no-download` or :option:`--cancel` are given."
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        metavar = "<directory>",
        type    = Path,
        nargs   = "?")

    # Register runner flags and arguments
    runner.register_runners(parser, exec = ["snakemake", "--printshellcmds", ...])

    return parser


def run(opts):
    assert_overlay_volumes_support(opts)

    # We must check this before the conditions under which opts.directory is
    # optional because otherwise we could pass a missing build dir to a runner
    # which ignores opts.attach.
    if (opts.attach or opts.detach or opts.detach_on_interrupt or opts.cancel) and opts.__runner__ is not runner.aws_batch:
        raise UserError(f"""
            The --attach, --detach, --detach-on-interrupt, and --cancel options
            are only supported when using the AWS Batch runtime.

            Did you forget to specify --aws-batch?
            """)

    # Interpret the given directory and ensure it exists if necessary.
    if opts.directory is not None:
        build_volume, working_volume = pathogen_volumes(opts.directory)

    else:
        if opts.attach and (not opts.download or opts.cancel):
            # Don't require a build directory with --attach + --no-download
            # or --attach + --cancel.  User just wants to check status/logs or
            # stop the job.
            build_volume = None
            working_volume = None
        else:
            raise UsageError("Path to a pathogen build <directory> is required.")

    if build_volume:
        opts.volumes.append(build_volume) # for Docker, Singularity, and AWS Batch


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

    return runner.run(opts, working_volume = working_volume, cpus = opts.cpus, memory = opts.memory)


def assert_overlay_volumes_support(opts):
    """
    Check that runtime overlays are supported, if given.
    """
    overlay_volumes = opts.volumes

    if not overlay_volumes:
        return

    if opts.__runner__ not in {docker, singularity, aws_batch}:
        raise UserError(f"""
            The {runner_name(opts.__runner__)} runtime does not support overlays (e.g. of {overlay_volumes[0].name}).
            Use the Docker, Singularity, or AWS Batch runtimes (via --docker,
            --singularity, or --aws-batch) if overlays are necessary.
            """)

    if opts.__runner__ is aws_batch and not docker.image_supports(docker.IMAGE_FEATURE.aws_batch_overlays, opts.image):
        raise UserError(f"""
            The Nextstrain runtime image version in use

                {opts.image}

            is too old to support overlays (e.g. of {overlay_volumes[0].name}) with AWS Batch.

            If overlays are necessary, please use at least version

                {split_image_name(opts.image)[0]}:{docker.IMAGE_FEATURE.aws_batch_overlays.value}

            of the runtime image.  The image used by AWS Batch can be changed
            using the --image option, the NEXTSTRAIN_DOCKER_IMAGE environment
            variable, or, if you also use the Docker runtime, by running
            `nextstrain update docker`.

            Alternatively, instead of AWS Batch you may use the Docker or
            Singularity runtime (via --docker or --singularity) which always
            support overlays regardless of image version.
            """)


def pathogen_volumes(directory: Path, *, name = "build") -> Tuple[NamedVolume, NamedVolume]:
    """
    Discern the pathogen **build volume** and **working volume** for a given
    *directory* path.

    The **build volume** is the pathogen repo root, if discernable by the
    presence of :file:`nextstrain-pathogen.yaml` in one of the parents of
    *directory*.  Otherwise, its the given *directory* as-is.

    The **working volume** is always the given *directory* labeled with a
    volume name that reflects its relative path within the **build volume**.

    Some examples:

    >>> build_volume, working_volume = pathogen_volumes(Path("tests/data/pathogen-repo/ingest/"))
    >>> build_volume # doctest: +ELLIPSIS
    NamedVolume(name='build', src=...Path('.../tests/data/pathogen-repo'), dir=True, writable=True)
    >>> working_volume # doctest: +ELLIPSIS
    NamedVolume(name='build/ingest', src=...Path('.../tests/data/pathogen-repo/ingest'), dir=True, writable=True)
    >>> docker.mount_point(build_volume) <= docker.mount_point(working_volume)
    True

    >>> build_volume, working_volume = pathogen_volumes(Path("tests/data/"))
    >>> build_volume # doctest: +ELLIPSIS
    NamedVolume(name='build', src=...Path('.../tests/data'), dir=True, writable=True)
    >>> working_volume # doctest: +ELLIPSIS
    NamedVolume(name='build', src=...Path('.../tests/data'), dir=True, writable=True)
    >>> docker.mount_point(build_volume) <= docker.mount_point(working_volume)
    True

    An alternative *name* for the **build volume** (and by extension the
    initial part of the name of the **working volume**) may be passed.

    >>> build_volume, working_volume = pathogen_volumes(Path("tests/data/pathogen-repo/ingest/"), name = "pathogen")
    >>> build_volume # doctest: +ELLIPSIS
    NamedVolume(name='pathogen', src=...Path('.../tests/data/pathogen-repo'), dir=True, writable=True)
    >>> working_volume # doctest: +ELLIPSIS
    NamedVolume(name='pathogen/ingest', src=...Path('.../tests/data/pathogen-repo/ingest'), dir=True, writable=True)
    """
    if not directory.is_dir():
        err = f"Build path {str(directory)!r} does not exist or is not a directory."

        if not directory.is_absolute():
            raise UserError(f"""
                {err}

                Perhaps your current working directory is different than you expect?
                """)
        else:
            raise UserError(err)

    # The pathogen repo root is (optionally) indicated by the presence of
    # nextstrain-pathogen.yaml.  We intentionally don't use a marker tied to
    # Git, i.e. .git/, because we and users sometimes run pathogen repos out of
    # exports from/snapshots of Git instead of full Git clones.
    #
    # Also, we have ideas for leveraging nextstrain-pathogen.yaml in the future
    # as a source of pathogen-level metadata for use in indexing, listing,
    # attribution, etc.  For now, the contents do not matter and an empty file
    # works just fine as the repo root marker.
    #   -trs, 29 Jan 2024
    marker_name = "nextstrain-pathogen.yaml"

    # Search upwards for pathogen repo root to serve as the build volume.
    working_dir = directory.resolve(strict = True)
    debug(f"Resolved {directory} to {working_dir}")

    debug(f"Looking for {marker_name} as pathogen root dir marker")

    for marker in (d / marker_name for d in [working_dir, *working_dir.parents]):
        if marker.exists():
            debug(f"{marker}: exists")
            build_volume = NamedVolume(name, marker.parent)
            break
        else:
            debug(f"{marker}: does not exist")
    else:
        build_volume = NamedVolume(name, working_dir)

    debug(f"Using {build_volume.src} as {name} volume")

    # Construct the working volume name based on its relative path within the
    # build volume we just determined.  The working volume should always be
    # within (or identical to) the build volume.
    working_volume = NamedVolume(
        str(PurePosixPath(build_volume.name) / working_dir.relative_to(build_volume.src)),
        working_dir)

    debug(f"Using {working_volume.src} as working ({working_volume.name}) volume")

    assert build_volume.src <= working_volume.src
    assert docker.mount_point(build_volume) <= docker.mount_point(working_volume)

    return build_volume, working_volume


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

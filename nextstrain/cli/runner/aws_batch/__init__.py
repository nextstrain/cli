"""
Run commands remotely on AWS Batch inside the Nextstrain container image.

`AWS Batch <https://aws.amazon.com/batch/>`__ is an advanced computing
platform which allows you to launch and monitor Nextstrain builds in the
cloud from the comfort of your own computer. The same image used by the local
Docker runtime is used by AWS Batch, making your builds more reproducible, and
builds have access to computers with very large CPU and memory allocations if
necessary.

.. versionadded:: 1.7.0


.. _aws-batch-setup:

Setup
=====

The initial setup is quite a bit more involved than most runtimes, but
:doc:`detailed instructions </aws-batch>` are available.

Once you've set up AWS, proceed with ``nextstrain setup aws-batch``.


.. _aws-batch-config:

Config file variables
=====================

Defaults for the corresponding command line options, specified in the
:doc:`config file </config/file>`.

.. glossary::

    :index:`aws-batch.job <configuration variable; aws-batch.job>`
        Default for ``--aws-batch-job``.

    :index:`aws-batch.queue <configuration variable; aws-batch.queue>`
        Default for ``--aws-batch-queue``.

    :index:`aws-batch.s3-bucket <configuration variable; aws-batch.s3-bucket>`
        Default for ``--aws-batch-bucket``.

    :index:`aws-batch.cpus <configuration variable; aws-batch.cpus>`
        Default for ``--aws-batch-cpus``.

    :index:`aws-batch.memory <configuration variable; aws-batch.memory>`
        Default for ``--aws-batch-memory``.


.. _aws-batch-env:

Environment variables
=====================

Defaults for the corresponding command line options, potentially overriding
defaults set by `config file variables`_.

.. envvar:: NEXTSTRAIN_AWS_BATCH_JOB

    Default for ``--aws-batch-job``.

.. envvar:: NEXTSTRAIN_AWS_BATCH_QUEUE

    Default for ``--aws-batch-queue``.

.. envvar:: NEXTSTRAIN_AWS_BATCH_S3_BUCKET

    Default for ``--aws-batch-bucket``.

.. envvar:: NEXTSTRAIN_AWS_BATCH_CPUS

    Default for ``--aws-batch-cpus``.

.. envvar:: NEXTSTRAIN_AWS_BATCH_MEMORY

    Default for ``--aws-batch-memory``.
"""

import botocore.exceptions
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from signal import signal, Signals, SIGINT
from sys import exit, stdin
from textwrap import dedent
from time import sleep, time
from typing import Iterable, Optional, cast
from uuid import uuid4
from ...types import Env, RunnerModule, SetupStatus, SetupTestResults, UpdateStatus
from ...util import colored, prose_list, runner_name, warn
from ... import config
from .. import docker
from . import jobs, s3


DEFAULT_JOB = os.environ.get("NEXTSTRAIN_AWS_BATCH_JOB") \
           or config.get("aws-batch", "job") \
           or "nextstrain-job"

DEFAULT_QUEUE = os.environ.get("NEXTSTRAIN_AWS_BATCH_QUEUE") \
             or config.get("aws-batch", "queue") \
             or "nextstrain-job-queue"

DEFAULT_S3_BUCKET = os.environ.get("NEXTSTRAIN_AWS_BATCH_S3_BUCKET") \
                 or config.get("aws-batch", "s3-bucket") \
                 or "nextstrain-jobs"

# defaults to None if enviroment or config is not set
DEFAULT_CPUS = os.environ.get("NEXTSTRAIN_AWS_BATCH_CPUS") \
            or config.get("aws-batch", "cpus")

# defaults to None if enviroment or config is not set
DEFAULT_MEMORY = os.environ.get("NEXTSTRAIN_AWS_BATCH_MEMORY") \
              or config.get("aws-batch", "memory")


CTRL_C_CONFIRMATION_TIMEOUT = 10 # seconds


def register_arguments(parser) -> None:
    # AWS Batch development options
    development = parser.add_argument_group(
        "development options for --aws-batch",
        "See <https://docs.nextstrain.org/projects/cli/page/aws-batch>\nfor more information.")

    development.add_argument(
        "--aws-batch-job",
        dest    = "job_definition",
        help    = "Name of the AWS Batch job definition to use",
        metavar = "<name>",
        default = DEFAULT_JOB)

    development.add_argument(
        "--aws-batch-queue",
        dest    = "job_queue",
        help    = "Name of the AWS Batch job queue to use",
        metavar = "<name>",
        default = DEFAULT_QUEUE)

    development.add_argument(
        "--aws-batch-s3-bucket",
        dest    = "s3_bucket",
        help    = "Name of the AWS S3 bucket to use as shared storage",
        metavar = "<name>",
        default = DEFAULT_S3_BUCKET)

    development.add_argument(
        "--aws-batch-cpus",
        dest    = "aws_batch_cpus",
        help    = "Number of vCPUs to request for job",
        metavar = "<count>",
        type    = int,
        default = DEFAULT_CPUS)

    development.add_argument(
        "--aws-batch-memory",
        dest    = "aws_batch_memory",
        help    = "Amount of memory in MiB to request for job",
        metavar = "<mebibytes>",
        type    = int,
        default = DEFAULT_MEMORY)


def run(opts, argv, working_volume = None, extra_env: Env = {}, cpus: int = None, memory: int = None) -> int:
    docker.assert_volumes_exist(opts.volumes)

    # "build" is a special-cased volume for AWS Batch, as /nextstrain/build is
    # the fixed initial working directory and what we'll populate by extracting
    # a ZIP file.
    build_volume = next((v for v in opts.volumes if v and v.name == "build"), None)

    opts.volumes = [v for v in opts.volumes if v is not build_volume]

    # Unlike other runners, the AWS Batch runner currently *requires* a working
    # dir in most usages.  This is ok as we only provide the AWS Batch runner
    # for commands which also require a working dir (e.g. build), whereas other
    # runners also work with commands that don't.
    #   -trs, 28 Feb 2022 (updated 24 August 2023)
    assert (working_volume is not None and build_volume is not None) or (opts.attach and (not opts.download or opts.cancel))

    # Note that "workdir" here always refers to our image's default WORKDIR,
    # /nextstrain/build, since AWS Batch provides no way to override the
    # initial working directory of a container, i.e. an equivalent to the
    # --workdir option of `docker run`.  Instead, to change the initial working
    # directory, we arrange to exec-chain thru `env --chdir`.
    #   -trs, 29 Jan 2024
    local_workdir = build_volume.src.resolve(strict = True) if build_volume else None

    if opts.attach:
        print_stage("Attaching to Nextstrain AWS Batch Job ID:", opts.attach)
        job = jobs.lookup(opts.attach)

        # Read remote workdir from the job description
        remote_workdir = job.workdir

        if not remote_workdir:
            warn(dedent("""
                Error determining remote workdir of job.

                This is probably a bug.  Please open an issue on GitHub
                <https://github.com/nextstrain/cli/issues/new> or send an
                email to <hello@nextstrain.org> for help.
                """))
            return 1

        print_stage("Job is %s" % job.status)
    else:
        assert local_workdir is not None
        assert working_volume is not None

        # Generate our own unique run id since we can't know the AWS Batch job id
        # until we submit it.  This run id is used for workdir and run results
        # storage on S3, in a bucket accessible to both Batch jobs and CLI users.
        run_id = generate_run_id()

        print_stage("Nextstrain Run ID:", run_id)

        # Upload workdir to S3 so it can be fetched at the start of the Batch job.
        print_stage("Uploading %s to S3" % local_workdir)

        for volume in opts.volumes:
            print("      and %s as %s" % (volume.src.resolve(strict = True), volume.name))

        bucket = s3.bucket(opts.s3_bucket)
        remote_workdir = s3.upload_workdir(local_workdir, bucket, run_id, opts.exclude_from_upload, opts.volumes)

        print("uploaded:", s3.object_url(remote_workdir))

        # If the image supports /nextstrain/env.d, then pass any env vars using
        # it so values aren't visible in the job's config (i.e. visible via
        # `aws batch describe-jobs` and the web console).
        if extra_env and docker.image_supports(docker.IMAGE_FEATURE.envd, opts.image):
            # Write out all env directly to a ZIP archive on S3…
            envd = s3.upload_envd(extra_env, bucket, run_id)

            print("uploaded:", s3.object_url(envd))

            # …then clear the env we pass via the job config and replace it
            # with the URL of the ZIP archive and a flag to delete the
            # /nextstrain/env.d contents and ZIP archive after use.
            extra_env = {
                "NEXTSTRAIN_ENVD_URL": s3.object_url(envd),
                "NEXTSTRAIN_DELETE_ENVD": "1" }

        # Submit job.
        print_stage("Submitting job")

        # Our own --aws-batch-cpus and --aws-batch-memory options take
        # precedence over whatever was passed from the command (e.g. the build
        # command's --cpus and --memory options).
        if opts.aws_batch_cpus:
            cpus = opts.aws_batch_cpus

        if opts.aws_batch_memory:
            memory = opts.aws_batch_memory
        elif memory:
            # Memory from our caller is in bytes, but AWS expects MiB.
            memory //= 1024**2

        # Change working directory in the container before running our command.
        # Note that this happens _after_ the build context we uploaded
        # (remote_workdir) is downloaded and extracted to the default working
        # directory (/nextstrain/build).
        exec = [
            "env", "--chdir", str(docker.mount_point(working_volume)), "--",
            *argv ]

        try:
            job = jobs.submit(
                name       = run_id,
                image      = opts.image,
                queue      = opts.job_queue,
                definition = opts.job_definition,
                cpus       = cpus,
                memory     = memory,
                workdir    = remote_workdir,
                exec       = exec,
                env        = { k: v for k, v in extra_env.items() if v is not None })
        except Exception as error:
            warn(error)
            warn("Job submission failed!")
            return 1

        print_stage("AWS Batch Job ID:", job.id)

        # Optionally detach and return early.
        if opts.detach:
            return detach(job, local_workdir)


    if opts.cancel:
        interrupt(job, confirm = False)


    # Don't setup signal handlers for jobs that are already complete or we're
    # stopping (cancelling).
    if not job.is_complete and not job.stop_sent:
        # Set up signal handler for SIGTSTP ("stop typed at terminal", e.g.
        # Ctrl-Z) and SIGHUP ("hangup detected on controlling terminal, or
        # death of controlling process").  Only Unix systems support these,
        # so we guard this non-essential feature.
        #
        # We leave SIGSTOP (non-TTY-generated stop signal) alone so standard
        # Unix process control with SIGSTOP and SIGCONT still works as usual.
        # Besides, SIGSTOP is not catchable!
        #
        # If modifying these, consider (re-)reading signal(7) first for
        # context.
        #   -trs, 29 August 2023
        SIGTSTP = getattr(Signals, "SIGTSTP", None)
        SIGHUP  = getattr(Signals, "SIGHUP", None)

        def detach_signaled(sig, frame):
            exit(detach(job, local_workdir))

        if SIGTSTP:
            signal(SIGTSTP, detach_signaled)
        if SIGHUP:
            signal(SIGHUP, detach_signaled)


        # Set up signal handler for SIGINT ("interrupt from keyboard", e.g.
        # Ctrl-C).
        #
        # We leave SIGTERM alone to allow `kill`'s default signal and other
        # standard Unix process control to work as usual.
        #   -trs, 29 August 2023
        if opts.detach_on_interrupt:
            signal(SIGINT, detach_signaled)
        else:
            def interrupt_signaled(sig, frame):
                if interrupt(job):
                    exit(128 + SIGINT)

            signal(SIGINT, interrupt_signaled)


        print_stage("Watching job status")

        if stdin.isatty():
            if opts.detach_on_interrupt:
                if SIGTSTP:
                    control_hints = """
                        Press Control-C or Control-Z to detach from this job.
                        """
                elif SIGHUP:
                    control_hints = """
                        Press Control-C or send SIGHUP to detach from this job.
                        """
                else:
                    control_hints = """
                        Press Control-C to detach from this job.
                        """
            else:
                if SIGTSTP:
                    control_hints = """
                        Press Control-C twice within %d seconds to cancel this job,
                              Control-Z to detach from it.
                        """ % (CTRL_C_CONFIRMATION_TIMEOUT,)
                elif SIGHUP:
                    control_hints = """
                        Press Control-C twice within %d seconds to cancel this job.
                         Send SIGHUP to detach from it.
                        """ % (CTRL_C_CONFIRMATION_TIMEOUT,)
                else:
                    control_hints = """
                        Press Control-C twice within %d seconds to cancel this job.
                        """ % (CTRL_C_CONFIRMATION_TIMEOUT,)
        else:
            if opts.detach_on_interrupt:
                sigs = prose_list(sig.name for sig in [SIGINT, SIGHUP, SIGTSTP] if sig)
                control_hints = f"""
                    Send {sigs} to detach from this job.
                    """
            else:
                if SIGHUP or SIGTSTP:
                    sigs = prose_list(sig.name for sig in [SIGHUP, SIGTSTP] if sig)
                    control_hints = f"""
                        Send SIGINT to cancel this job,
                             {sigs} to detach from it.
                        """
                else:
                    control_hints = """
                        Send SIGINT to cancel this job.
                        """

        print(dedent(control_hints))


    # Watch job status and tail logs.
    log_watcher = None

    while True:
        job.update()

        # Inform the user of intermediate status changes.  Final status changes
        # are messaged separately below.
        if job.status_changed and not job.is_complete:
            print_stage("Job now %s" % job.status)

        if job.is_running and not log_watcher:
            # Transitioned from waiting → running, so kick off the log watcher.
            if opts.logs:
                log_watcher = job.log_watcher(consumer = print_job_log)
                log_watcher.start()

        elif job.is_complete:
            if log_watcher:
                if log_watcher.is_alive():
                    log_watcher.stop()
                log_watcher.join()
            else:
                # The watcher never started, so we probably missed the
                # transition to running.  Display the whole log now!
                if opts.logs:
                    try:
                        for entry in job.log_entries():
                            print_job_log(entry)
                    except botocore.exceptions.ClientError as error:
                        warn(f"Unable to fetch job logs: {error}")

            print_stage(
                "Job %s after %0.1f minutes" % (job.status, job.elapsed_time / 60),
                "(%s)" % job.status_reason)
            break

        # Only check status every 6s (10 times per minute).
        sleep(6)


    # Download results if we didn't stop the job early.
    if opts.download and not job.stop_sent and not job.stopped:
        assert local_workdir is not None

        patterns = opts.download if isinstance(opts.download, list) else None

        if patterns:
            print_stage("Downloading select files modified by job to %s" % local_workdir)
            for pattern in patterns:
                print("  - %s" % pattern)
        else:
            print_stage("Downloading all files modified by job to %s" % local_workdir)

        s3.download_workdir(remote_workdir, local_workdir, patterns)


    # Exit with the job's exit code if available or 1 if another failure,
    # otherwise success.
    return (
        job.exit_code if job.exit_code is not None else
                    1 if job.is_failed             else
                    0
    )


interrupt_called = 0

def interrupt(job: jobs.JobState, confirm: bool = stdin.isatty()) -> bool:
    """
    Request interruption (cancellation) of the specified *job* and wait for it
    to exit.

    Prints status messages about what's going on.

    If *confirm* is ``True``, by default when a TTY is attached to stdin, then
    this function must be invoked at least twice within the
    ``CTRL_C_CONFIRMATION_TIMEOUT`` to actually cancel the job.

    Returns ``True`` if the process should exit immediately, i.e. not wait for
    the job to exit first.  Otherwise, returns ``False``.
    """
    global interrupt_called

    print()

    # Exit immediately the job is already complete or has already been stopped
    # (e.g. by a previous double Ctrl-C).
    if job.is_complete or job.stop_sent:
        return True

    now = int(time())

    if confirm and now - interrupt_called > CTRL_C_CONFIRMATION_TIMEOUT:
        interrupt_called = now

        if stdin.isatty():
            print_stage("Press Control-C again within %d seconds to cancel this job." % (CTRL_C_CONFIRMATION_TIMEOUT,))
        else:
            print_stage("Send SIGINT again within %d seconds to cancel this job." % (CTRL_C_CONFIRMATION_TIMEOUT,))
    else:
        print_stage("Canceling job…")
        job.stop()

        print_stage("Waiting for job to stop…")
        if stdin.isatty():
            print(f"(Press Control-C {'one more time ' if confirm else ''}if you don't want to wait.)")
        else:
            print(f"(Send SIGINT {'one more time ' if confirm else ''}if you don't want to wait.)")

    return False


def detach(job: jobs.JobState, local_workdir: Optional[Path]) -> int:
    """
    Detach from the specified *job* and print a message about how to re-attach
    (using the *local_workdir*).
    """
    print("")
    print_stage("Detaching from job, as requested")

    reattach_cmd = " ".join([
        "nextstrain",
        "build",
        "--aws-batch",
        "--attach", shlex.quote(job.id),

        # Preserve the local workdir, which has been resolved to an absolute path
        shlex.quote(str(local_workdir) if local_workdir else ".")
    ])

    print(dedent("""
        Run the following command to re-attach to this job later to see output
        and download results:

        %s""") % (reattach_cmd,))

    return 0


def print_stage(stage, *args):
    """
    Print the current running stage, nicely formatted.
    """
    return print(colored("bold", stage), *args)


def print_job_log(entry):
    """
    Print an AWS Batch job log entry.
    """
    msg = entry.get("message", "")
    ts = entry.get("timestamp", entry.get("ingestionTime")) # milliseconds since epoch

    if ts is not None:
        ts = datetime.fromtimestamp(round(ts / 1000)).astimezone().isoformat()
        print(f"[batch] [{ts}] {msg}")
    else:
        print(f"[batch] {msg}")


def generate_run_id() -> str:
    """
    Return a globally unique ID string identifying a run.

    Currently this is just a version 4 UUID (GUID).
    """
    return str(uuid4())


def setup(dry_run: bool = False, force: bool = False) -> SetupStatus:
    """
    Not supported.
    """
    return None


def test_setup() -> SetupTestResults:
    """
    Check that necessary AWS resources exist.
    """
    yield ('job description "%s" exists' % DEFAULT_JOB,
            jobs.definition_exists(DEFAULT_JOB))

    yield ('job queue "%s" exists' % DEFAULT_QUEUE,
            jobs.queue_exists(DEFAULT_QUEUE))

    yield ('S3 bucket "%s" exists' % DEFAULT_S3_BUCKET,
            s3.bucket_exists(DEFAULT_S3_BUCKET))


def set_default_config() -> None:
    """
    Sets ``core.runner`` to this runner's name (``aws-batch``).
    """
    config.set("core", "runner", runner_name(cast(RunnerModule, sys.modules[__name__])))


def update() -> UpdateStatus:
    """
    Not supported.  Updating the AWS Batch runtime isn't meaningful.
    """
    return None


def versions() -> Iterable[str]:
    """
    No-op.  Since batch jobs are non-interactive, there's no good way to
    extract meaningful versions from them.  Perhaps the job definition
    revision would be useful, but maybe not?
    """
    return []

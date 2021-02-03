"""
Run commands remotely on AWS Batch inside the Nextstrain container image.
"""

import os
import shlex
import signal
import subprocess
from pathlib import Path
from sys import exit
from textwrap import dedent
from time import sleep, time
from typing import Iterable
from uuid import uuid4
from ...types import RunnerTestResults, Tuple
from ...util import colored, resolve_path, warn
from ... import config
from . import jobs, logs, s3


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
        "See <https://github.com/nextstrain/cli/tree/master/doc/aws-batch.md>\nfor more information.")

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


def run(opts, argv, working_volume = None, extra_env = {}, cpus: int = None, memory: int = None) -> int:
    local_workdir = resolve_path(working_volume.src)

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
        # Generate our own unique run id since we can't know the AWS Batch job id
        # until we submit it.  This run id is used for workdir and run results
        # storage on S3, in a bucket accessible to both Batch jobs and CLI users.
        run_id = generate_run_id()

        print_stage("Nextstrain Run ID:", run_id)

        # Upload workdir to S3 so it can be fetched at the start of the Batch job.
        print_stage("Uploading %s to S3" % local_workdir)

        bucket = s3.bucket(opts.s3_bucket)
        remote_workdir = s3.upload_workdir(local_workdir, bucket, run_id)

        print("uploaded:", s3.object_url(remote_workdir))


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

        try:
            job = jobs.submit(
                name       = run_id,
                image      = opts.image,
                queue      = opts.job_queue,
                definition = opts.job_definition,
                cpus       = cpus,
                memory     = memory,
                workdir    = remote_workdir,
                exec       = argv,
                env        = extra_env)
        except Exception as error:
            warn(error)
            warn("Job submission failed!")
            return 1

        print_stage("AWS Batch Job ID:", job.id)

        # Optionally detach and return early.
        if opts.detach:
            return detach(job, local_workdir)


    # Setup signal handler for Ctrl-Z.  Only Unix systems support SIGTSTP, so
    # we guard this non-essential feature.
    try:
        SIGTSTP = signal.SIGTSTP
    except AttributeError:
        SIGTSTP = None # type: ignore
    else:
        def handler(sig, frame):
            exit(detach(job, local_workdir))
        signal.signal(SIGTSTP, handler)


    # Watch job status and tail logs.
    print_stage("Watching job status")

    if SIGTSTP:
        control_hints = """
            Press Control-C twice within %d seconds to cancel this job,
                  Control-Z to detach from it.
            """ % (CTRL_C_CONFIRMATION_TIMEOUT,)
    else:
        control_hints = """
            Press Control-C twice within %d seconds to cancel this job.
            """ % (CTRL_C_CONFIRMATION_TIMEOUT,)

    print(dedent(control_hints))

    log_watcher = None
    stop_sent = False
    ctrl_c_time = 0

    while True:
        # This try/except won't catch KeyboardInterrupts which happen in the
        # narrow window of time between the job submission above and this loop
        # (or between iterations of the loop).  Handling those extreme edge
        # cases will make this whole run() function much less clear, and I
        # don't think its worth it for what's ultimately a convenience feature.
        #   -trs, 12 Oct 2018
        try:
            job.update()

            # Inform the user of intermediate status changes.  Final status changes
            # are messaged separately below.
            if job.status_changed and not job.is_complete:
                print_stage("Job now %s" % job.status)

            if job.is_running and not log_watcher:
                # Transitioned from waiting → running, so kick off the log watcher.
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
                    for entry in job.log_entries():
                        print_job_log(entry)

                print_stage(
                    "Job %s after %0.1f minutes" % (job.status, job.elapsed_time / 60),
                    "(%s)" % job.status_reason)
                break

            # Only check status every 6s (10 times per minute).
            sleep(6)

        except KeyboardInterrupt as interrupt:
            print()

            if not stop_sent:
                now = int(time())

                if now - ctrl_c_time > CTRL_C_CONFIRMATION_TIMEOUT:
                    ctrl_c_time = now
                    print_stage("Press Control-C again within %d seconds to cancel this job." % (CTRL_C_CONFIRMATION_TIMEOUT,))
                else:
                    print_stage("Canceling job…")
                    job.stop()

                    stop_sent = True

                    print_stage("Waiting for job to stop…")
                    print("(Press Control-C one more time if you don't want to wait.)")
            else:
                raise interrupt from None


    # Download results if we didn't stop the job early.
    if opts.download and not stop_sent and not job.stopped:
        patterns = opts.download if isinstance(opts.download, list) else None

        if patterns:
            print_stage("Downloading select files modified by job to %s" % local_workdir)
            for pattern in patterns:
                print("  - %s" % pattern)
        else:
            print_stage("Downloading all files modified by job to %s" % local_workdir)

        s3.download_workdir(remote_workdir, local_workdir, patterns)


    # Exit with the job's exit code, or assume success
    return job.exit_code or 0


def detach(job: jobs.JobState, local_workdir: Path) -> int:
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
        shlex.quote(str(local_workdir))
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
    print("[batch]", entry.get("message", ""))


def generate_run_id() -> str:
    """
    Return a globally unique ID string identifying a run.

    Currently this is just a version 4 UUID (GUID).
    """
    return str(uuid4())


def test_setup() -> RunnerTestResults:
    """
    Check that necessary AWS resources exist.
    """
    return [
        ('job description "%s" exists' % DEFAULT_JOB,
            jobs.definition_exists(DEFAULT_JOB)),

        ('job queue "%s" exists' % DEFAULT_QUEUE,
            jobs.queue_exists(DEFAULT_QUEUE)),

        ('S3 bucket "%s" exists' % DEFAULT_S3_BUCKET,
            s3.bucket_exists(DEFAULT_S3_BUCKET)),
    ]


def update() -> bool:
    """
    No-op.  Updating the AWS Batch environment isn't meaningful.
    """
    return True


def versions() -> Iterable[str]:
    """
    No-op.  Since batch jobs are non-interactive, there's no good way to
    extract meaningful versions from them.  Perhaps the job definition
    revision would be useful, but maybe not?
    """
    return []

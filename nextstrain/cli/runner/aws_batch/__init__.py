"""
Run commands remotely on AWS Batch inside the Nextstrain container image.
"""

import os
import shutil
import subprocess
from pathlib import Path
from time import sleep
from uuid import uuid4
from ...types import RunnerTestResults
from ...util import colored, warn
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


def run(opts, argv, working_volume = None) -> int:
    # Generate our own unique run id since we can't know the AWS Batch job id
    # until we submit it.  This run id is used for workdir and run results
    # storage on S3, in a bucket accessible to both Batch jobs and CLI users.
    run_id = generate_run_id()

    print_stage("Nextstrain Run ID:", run_id)


    # Upload workdir to S3 so it can be fetched at the start of the Batch job.
    local_workdir = working_volume.src.resolve()

    print_stage("Uploading %s to S3" % local_workdir)

    bucket = s3.bucket(opts.s3_bucket)
    remote_workdir = s3.upload_workdir(local_workdir, bucket, run_id)

    print("uploaded:", s3.object_url(remote_workdir))


    # Submit job.
    print_stage("Submitting job")

    try:
        job = jobs.submit(
            name       = run_id,
            queue      = opts.job_queue,
            definition = opts.job_definition,
            workdir    = remote_workdir,
            exec       = argv)
    except Exception as error:
        warn(error)
        warn("Job submission failed!")
        return 1

    print_stage("AWS Batch Job ID:", job.id)

    # XXX TODO: It might be nice in the future to support an --unattended
    # option which stops at this point and prompts you to download results
    # later using the run id, e.g.
    #
    #    nextstrain build --aws-batch --resume 5d0a102e-df3e-418a-aef7-3283ea77563a zika/
    #
    # I planned support for this originally but am punting on it for now in the
    # interest of getting this feature out the door.
    #   -trs, 14 Sept 2018

    # Watch job status and tail logs.
    print_stage("Watching job status")

    log_watcher = None
    stop_sent = False

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

            if job.is_running and job.was_waiting:
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
                print_stage("Canceling job…")
                job.stop()

                print_stage("Waiting for job to stop…")
                print("(Press Ctrl-C again if you don't want to wait.)")

                stop_sent = True
            else:
                raise interrupt from None


    # Download results if we didn't stop the job early.
    if not stop_sent:
        print_stage("Downloading files modified by job to %s" % local_workdir)

        s3.download_workdir(remote_workdir, local_workdir)


    # Remove remote results.
    print_stage("Cleaning up S3")

    remote_workdir.delete()

    print("deleted:", s3.object_url(remote_workdir))


    # Remove log stream.
    if job.log_stream:
        print_stage("Cleaning up logs")

        logs.delete_stream(job.log_stream)

        print("deleted log stream:", job.log_stream)


    # Exit with the job's exit code, or assume success
    return job.exit_code or 0


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


def print_version() -> None:
    """
    No-op.  Since batch jobs are non-interactive, there's no good way to
    extract meaningful versions from them.  Perhaps the job definition
    revision would be useful, but maybe not?
    """
    pass

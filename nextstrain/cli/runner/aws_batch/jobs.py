"""
Job handling for AWS Batch.
"""

from time import time
from typing import Callable, Generator, Iterable, List, Optional
from ... import hostenv, aws
from . import logs, s3


class JobState:
    """
    Query and present AWS Batch job state.

    Abstracts away some of the AWS Batch job details into a simpler state
    object.  Call update() to fetch the initial state and again to subsequently
    refresh it.
    """

    INITIAL_STATUS  = { 'SUBMITTED', 'PENDING', 'RUNNABLE', 'STARTING' }
    RUNNING_STATUS  = { 'RUNNING' }
    TERMINAL_STATUS = { 'SUCCEEDED', 'FAILED' }

    def __init__(self, job_id):
        self.id              = job_id
        self.state           = {}
        self.previous_status = None
        self._client         = aws.client_with_default_region("batch")

    def update(self) -> None:
        """
        Fetch the latest state for this job, replacing the previously cached
        state.
        """
        self.previous_status = self.status
        self.state = self._client.describe_jobs(jobs = [ self.id ])["jobs"][0]

    @property
    def status(self) -> str:
        return self.state.get("status", "UNKNOWN")

    @property
    def status_changed(self) -> bool:
        return self.status != self.previous_status

    @property
    def status_reason(self) -> Optional[str]:
        reason = self.state.get("statusReason")

        # Make the default/normal reason more informative
        if reason == "Essential container in task exited":
            if self.exit_code is not None:
                return "exited %d" % self.exit_code
            else:
                return "exited"
        else:
            return reason

    @property
    def is_waiting(self) -> bool:
        return self.status in self.INITIAL_STATUS

    @property
    def was_waiting(self) -> bool:
        return self.previous_status in self.INITIAL_STATUS

    @property
    def is_running(self) -> bool:
        return self.status in self.RUNNING_STATUS

    @property
    def is_complete(self) -> bool:
        return self.status in self.TERMINAL_STATUS

    @property
    def elapsed_time(self) -> float:
        # Timestamps from the job state are in milliseconds
        created = self.state.get("createdAt", float("NaN"))  / 1000
        stopped = self.state.get("stoppedAt", time() * 1000) / 1000
        return stopped - created

    @property
    def log_stream(self) -> Optional[str]:
        return self.state.get("container", {}).get("logStreamName")

    @property
    def exit_code(self) -> Optional[int]:
        return self.state.get("container", {}).get("exitCode")

    def log_entries(self) -> Generator[dict, None, None]:
        """
        Fetch all the CloudWatch log entries for this job.

        Returns a generator which yields dict objects.
        """
        if self.log_stream:
            yield from logs.fetch_stream(self.log_stream)
        else:
            yield from []

    def log_watcher(self, consumer: Callable[[dict], None]) -> logs.LogWatcher:
        """
        Monitor the CloudWatch log stream for this job and call the supplied
        *consumer* function with each log entry.

        Returns a LogWatcher thread object, which the caller must start().
        """
        assert self.log_stream, "No log stream for job"

        return logs.LogWatcher(self.log_stream, consumer)

    def stop(self, reason = "stopped by user") -> None:
        """
        Stop the job, regardless of if it has started yet or not.
        """
        self._client.terminate_job(jobId = self.id, reason = reason)


def submit(name: str,
           queue: str,
           definition: str,
           workdir: s3.S3Object,
           exec: Iterable[str]) -> JobState:
    """
    Submit a job to AWS Batch.

    Returns a JobState object.
    """
    batch = aws.client_with_default_region("batch")

    submission = batch.submit_job(
        jobName = name,
        jobQueue = queue,
        jobDefinition = definition,
        containerOverrides = {
            "environment": [
                {
                    "name": "NEXTSTRAIN_AWS_BATCH_WORKDIR_URL",
                    "value": s3.object_url(workdir),
                },
                *forwarded_environment(),
            ],
            "command": [
                "/sbin/entrypoint-aws-batch",
                *exec
            ]
        }
    )

    job_id = submission["jobId"]

    return JobState(job_id)


def forwarded_environment() -> List[dict]:
    """
    Return a list of Batch job environment entries for the ambient local host
    environment we want to forward along.
    """

    # XXX TODO: This isn't great from a security perspective as it makes the
    # secrets visible in the AWS Batch job descriptions and possibly even the
    # underlying Docker invocations in the process list on our
    # dynamically-provisioned EC2 instances.  It probably ends up in logs
    # somewhere too.  Naturally, Amazon recommends against it:
    #
    #    https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html#containerProperties
    #
    # A better approach to implement in the future would be writing an env dir,
    # shipping it over S3 like the rest of the job context, and adding envdir
    # into the entrypoint exec-chain.
    #
    # I'm punting on that in the immediate-term as the risk/threat seems low,
    # especially as our AWS Batch queue will only be used by ourselves.  (Other
    # people will have to setup their own Batch queue.)
    #   -trs, 17 Sept 2018
    return [
        { "name": name, "value": value }
            for name, value in hostenv.forwarded_values()
    ]


def definition_exists(name: str) -> bool:
    """
    Test if an AWS Batch job definition exists.
    """
    try:
        batch = aws.client_with_default_region("batch")

        return bool(
            batch.describe_job_definitions(jobDefinitionName = name, status = 'ACTIVE') \
                 .get("jobDefinitions"))
    except:
        return False


def queue_exists(name: str) -> bool:
    """
    Test if an AWS Batch job queue exists.
    """
    try:
        batch = aws.client_with_default_region("batch")

        return bool(
            batch.describe_job_queues(jobQueues = [name]) \
                 .get("jobQueues"))
    except:
        return False

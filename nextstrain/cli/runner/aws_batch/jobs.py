"""
Job handling for AWS Batch.
"""

import re
from botocore.exceptions import ClientError
from copy import deepcopy
from operator import itemgetter
from time import time
from typing import Callable, Generator, Iterable, Mapping, List, Optional
from ... import hostenv, aws
from ...errors import UserError
from ...util import split_image_name
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

    STOP_REASON = "stopped by user"

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

        jobs = self._client.describe_jobs(jobs = [ self.id ])["jobs"]

        try:
            self.state = jobs[0]
        except IndexError as error:
            raise ValueError("Invalid or unknown job id %s" % self.id) from None

    @property
    def status(self) -> str:
        return self.state.get("status", "UNKNOWN")

    @property
    def status_changed(self) -> bool:
        return self.status != self.previous_status

    @property
    def status_reason(self) -> Optional[str]:
        reason = self.state.get("statusReason")
        container_reason = self.state.get("container", {}).get("reason")

        # Make the default/normal reason more informative
        if reason == "Essential container in task exited":
            if self.exit_code is not None:
                reason = "exited %d" % self.exit_code
            else:
                reason = "exited"

        if reason and container_reason:
            return "%s, %s" % (container_reason, reason)
        else:
            return reason or container_reason

    @property
    def is_waiting(self) -> bool:
        return self.status in self.INITIAL_STATUS

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

    @property
    def workdir(self) -> Optional[str]:
        env = {
            var["name"]: var["value"]
                for var in self.state.get("container", {}).get("environment", []) }

        url = env.get("NEXTSTRAIN_AWS_BATCH_WORKDIR_URL")

        return s3.object_from_url(url) if url else None

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

    def stop(self) -> None:
        """
        Stop the job, regardless of if it has started yet or not.
        """
        self._client.terminate_job(jobId = self.id, reason = self.STOP_REASON)

    @property
    def stopped(self) -> bool:
        return self.status_reason == self.STOP_REASON


def submit(name: str,
           image: str,
           queue: str,
           definition: str,
           cpus: Optional[int],
           memory: Optional[int],
           workdir: s3.S3Object,
           exec: Iterable[str],
           env: Mapping = {}) -> JobState:
    """
    Submit a job to AWS Batch.

    Returns a JobState object.
    """
    batch = aws.client_with_default_region("batch")

    submission = batch.submit_job(
        jobName = name,
        jobQueue = queue,
        jobDefinition = override_definition(definition, image),
        containerOverrides = {
            "environment": [
                {
                    "name": "NEXTSTRAIN_AWS_BATCH_WORKDIR_URL",
                    "value": s3.object_url(workdir),
                },
                *forwarded_environment(),
                *[{"name": name, "value": value} for name, value in env.items()]
            ],
            **({ "vcpus": cpus } if cpus else {}),
            **({ "memory": memory } if memory else {}),
            "command": [
                "/sbin/entrypoint-aws-batch",
                *exec
            ]
        }
    )

    job_id = submission["jobId"]

    return JobState(job_id)


def lookup(job_id: str) -> JobState:
    """
    Lookup an AWS Batch job by its id.

    Returns a JobState object.
    """
    job = JobState(job_id)
    job.update()
    return job


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


def override_definition(base_definition_name: str, image: str) -> str:
    """
    Find or create a job definition based on *base_definition_name* but which
    uses *image*.

    *base_definition_name* must already exist.  If it uses *image* itself, it
    will be returned as-is.  Otherwise, a new derived job definition will be
    created to override *image*.

    This function only exists because the ``containerOverrides`` data structure
    used in job submission doesn't support overriding the image.

    Returns a job definition name.
    """
    # XXX TODO: We only create derived job definitions from an existing base
    # definition, which is minimally modified.  This is a conservative choice
    # that avoids hardcoding a default definition.  In the future, we might
    # consider relaxing this to auto-create a default base definition.  The
    # advantage there is one less piece of initial AWS setup.  The challenge is
    # choosing defaults that work for everyone's taste for resources/spending,
    # as well as using the right job roles and other details.
    #   -trs, 22 May 2020
    batch = aws.client_with_default_region("batch")

    base_definition = lookup_definition(base_definition_name)

    if not base_definition:
        raise UserError("AWS Batch job definition «%s» does not exist" % base_definition_name)

    # The base definition might already use this image, in which case we avoid
    # creating anything.  This lets admins not grant job definition creation to
    # users if they want; users will instead have to specify matching
    # --aws-batch-job and --image values.
    #
    # Split the image name in order to normalize the implicit :latest tag.
    base_image = base_definition["containerProperties"]["image"]

    if split_image_name(base_image) == split_image_name(image):
        return base_definition_name

    # The revision of the base definition is included in the derived image name
    # so that changes to the base definition cause derived definitions to be
    # re-created.  Unfortunately, we can't explicitly set the revision of new
    # definitions.
    derived_definition_name = sanitize_name(
        "_".join((
            base_definition_name,
            str(base_definition["revision"]),
            *split_image_name(image))))

    derived_definition = lookup_definition(derived_definition_name)

    if not derived_definition:
        derived_definition = deepcopy(base_definition)
        derived_definition["jobDefinitionName"] = derived_definition_name
        derived_definition["containerProperties"]["image"] = image

        # These are AWS-assigned keys returned by describe_job_definitions() which
        # aren't supported as keyword arguments by register_job_definition().
        for key in {'jobDefinitionArn', 'revision', 'status'}:
            del derived_definition[key]

        batch.register_job_definition(**derived_definition)
    else:
        derived_image = derived_definition["containerProperties"]["image"]

        assert split_image_name(derived_image) == split_image_name(image), (
            "Expected job definition «%s», derived from «%s», to use image «%s», "
            "but it uses «%s» instead"
            % (derived_definition_name, base_definition_name, image, derived_image))

    return derived_definition_name


def lookup_definition(name: str) -> Optional[dict]:
    """
    Lookup an AWS Batch job definition by its *name*.

    Always returns the latest active revision.

    Returns a dict if found, ``None`` if not.
    """
    batch = aws.client_with_default_region("batch")

    active = batch.describe_job_definitions(jobDefinitionName = name, status = 'ACTIVE')

    revisions = sorted(
        active["jobDefinitions"],
        key = itemgetter("revision"),
        reverse = True)

    return revisions[0] if revisions else None


def sanitize_name(name: str) -> str:
    """
    Mangles *name* to fit within a job or job definition name.

    * Replaces any invalid character with a hyphen ``-``
    * Truncates to 128 characters in length
    """
    return re.sub(r"[^A-Za-z0-9_-]", "-", name)[0:128]


def definition_exists(name: str) -> bool:
    """
    Test if an AWS Batch job definition exists.
    """
    try:
        return bool(lookup_definition(name))
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

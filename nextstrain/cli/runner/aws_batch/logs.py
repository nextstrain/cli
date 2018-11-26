"""
Log handling for AWS Batch jobs.
"""

import threading
from typing import Callable, Generator, Mapping, MutableSet
from ... import aws


LOG_GROUP = "/aws/batch/job"


def fetch_stream(stream: str, start_time: int = None) -> Generator[dict, None, None]:
    """
    Fetch all log entries from the named AWS Batch job *stream*.  Returns a
    generator.

    If the *start_time* argument is given, only entries with timestamps on or
    after the given value are fetched.
    """

    client = aws.client_with_default_region("logs")

    log_events = client.get_paginator("filter_log_events")

    query = {
        "logGroupName": LOG_GROUP,
        "logStreamNames": [ stream ],
    } # type: dict

    if start_time:
        query["startTime"] = start_time

    for page in log_events.paginate(**query):
        yield from page.get("events", [])


def delete_stream(stream: str) -> None:
    """
    Delete the named AWS Batch job log *stream*.  Returns nothing.
    """
    client = aws.client_with_default_region("logs")

    client.delete_log_stream(
        logGroupName  = LOG_GROUP,
        logStreamName = stream)


class LogWatcher(threading.Thread):
    """
    Monitor an AWS Batch job log stream and call a supplied function (the
    *consumer*) with each log entry.

    This is a Thread.  Call start() to begin monitoring the log stream and
    stop() (and then join()) to stop.
    """

    def __init__(self, stream: str, consumer: Callable[[dict], None]) -> None:
        super().__init__(name = "log-watcher", daemon = True)
        self.stream   = stream
        self.consumer = consumer
        self.stopped  = threading.Event()

    def stop(self) -> None:
        """
        Tell the log watcher to cease watching for new logs.

        This method merely signals to the thread that it should stop, so you
        must call the thread's join() method afterwards to wait for the thread
        to exit.  It is an error to call stop() on a thread which isn't alive
        (running).
        """
        assert self.is_alive(), "Thread not alive"
        self.stopped.set()

    def run(self) -> None:
        """
        Watch for new logs and pass each log entry to the "consumer" function.
        """

        # Track the last timestamp we see.  When we fetch_stream() again on the
        # next iteration, we'll start from that timestamp onwards to avoid
        # fetching every single page again.  The last event or two will be
        # still be in the response, but our de-duping will ignore those.
        last_timestamp = None

        # Keep track of what log entries we've consumed so that we suppress
        # duplicates.  Duplicates will arise in our stream due to the way we
        # watch for new entries.
        consumed = set()    # type: MutableSet

        while not self.stopped.wait(0.2):
            for entry in fetch_stream(self.stream, start_time = last_timestamp):
                if entry["eventId"] not in consumed:
                    consumed.add(entry["eventId"])

                    last_timestamp = entry["timestamp"]

                    self.consumer(entry)

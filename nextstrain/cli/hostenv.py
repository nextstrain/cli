"""
Translation of local host environment to the runner (build) environments.
"""

import os
from typing import List, Tuple


# Host environment variables to pass through (forward) into the Nextstrain
# build/runner environments (e.g. the Docker container or AWS Batch job).  This
# is intended to be a central, authoritative list.

forwarded_names = [
    # RethinkDB credentials
    "RETHINK_HOST",
    "RETHINK_AUTH_KEY",
]


def forwarded_values() -> List[Tuple[str, str]]:
    """
    Return a list of (name, value) tuples for the ``hostenv.forwarded_names``
    defined in the current ``os.environ``.

    Values may be sensitive credentials, so if at all possible, values returned
    from this should generally be omitted from command-line invocations and
    similar widely-visible contexts.
    """

    return [
        (name, os.environ.get(name, ""))
            for name in forwarded_names
             if name in os.environ
    ]

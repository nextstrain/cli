"""
HTTP requests and responses with consistent defaults for us.

.. envvar:: NEXTSTRAIN_CLI_USER_AGENT_MINIMAL

    Set to a truthy value (e.g. 1) to send only a minimal `User-Agent header
    <https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/User-Agent>`__
    in HTTP requests.

    The minimal User-Agent header includes just the Nextstrain CLI version,
    e.g.::

        Nextstrain-CLI/9.0.0 (https://nextstrain.org/cli)

    The full User-Agent header normally sent with requests includes basic
    information on several important software components, e.g.::

        Nextstrain-CLI/9.0.0 (https://nextstrain.org/cli) Python/3.10.9 python-requests/2.32.3 platform/Linux-x86_64 installer/standalone tty/yes

    This information is non-identifying and useful for our troubleshooting and
    aggregate usage metrics, so we do not recommend omitting it unless
    necessary.
"""
import certifi
import os
import platform
import requests
import sys
from functools import lru_cache
from typing import Tuple

# Import these for re-export for better drop-in compatibility
# with existing callers.
import requests.auth as auth                                        # noqa: F401
import requests.exceptions as exceptions                            # noqa: F401
import requests.utils as utils                                      # noqa: F401
from requests import PreparedRequest, RequestException, Response    # noqa: F401

from .__version__ import __version__


USER_AGENT_MINIMAL = bool(os.environ.get("NEXTSTRAIN_CLI_USER_AGENT_MINIMAL"))

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") \
         or os.environ.get("CURL_CA_BUNDLE") \
         or certifi.where()


class Session(requests.Session):
    def __init__(self):
        super().__init__()

        # Add our own user agent with useful information
        self.headers["User-Agent"] = default_user_agent()


def get(*args, **kwargs) -> Response:
    with Session() as session:
        return session.get(*args, **kwargs)

def post(*args, **kwargs) -> Response:
    with Session() as session:
        return session.post(*args, **kwargs)


@lru_cache(maxsize = None)
def default_user_agent(minimal: bool = USER_AGENT_MINIMAL) -> str:
    """
    Returns an informative user-agent for ourselves.

    If *minimal*, only our own version is included.  Otherwise, useful
    information on several components is also included.

    Format complies with `RFC 9110
    <https://datatracker.ietf.org/doc/html/rfc9110#name-user-agent>`__.
    """
    if minimal:
        return f"Nextstrain-CLI/{__version__} (https://nextstrain.org/cli)"

    py_version = version_info_to_str(sys.version_info)

    from .util import distribution_installer # import here to avoid import cycle
    installer = distribution_installer() or "unknown"

    system  = platform.system()
    machine = platform.machine()

    tty = "yes" if any(os.isatty(fd) for fd in [0, 1, 2]) else "no"

    return f"Nextstrain-CLI/{__version__} (https://nextstrain.org/cli) Python/{py_version} python-requests/{requests.__version__} platform/{system}-{machine} installer/{installer} tty/{tty}"


def version_info_to_str(version_info: Tuple[int, int, int, str, int]) -> str:
    """
    Convert a :attr:`sys.version_info` tuple (or lookalike) to its canonical
    string representation.

    >>> version_info_to_str((1, 2, 3, "final", 0))
    '1.2.3'
    >>> version_info_to_str((1, 2, 3, "alpha", 0))
    '1.2.3a0'
    >>> version_info_to_str((1, 2, 3, "beta", 1))
    '1.2.3b1'
    >>> version_info_to_str((1, 2, 3, "candidate", 2))
    '1.2.3rc2'
    >>> version_info_to_str((1, 2, 3, "bogus", 3))
    '1.2.3bogus3'
    """
    major, minor, micro, releaselevel, serial = version_info

    if pre := {"alpha":"a", "beta":"b", "candidate":"rc", "final":""}.get(releaselevel, releaselevel):
        pre += str(serial)

    return f"{major}.{minor}.{micro}{pre}"

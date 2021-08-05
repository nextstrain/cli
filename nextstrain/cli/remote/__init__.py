"""
Remote destinations and sources for Nextstrain datasets and narratives.
"""

from typing import cast, Tuple, TYPE_CHECKING
from urllib.parse import urlparse, ParseResult
from ..errors import UserError
from ..types import RemoteModule
from . import (
    s3 as __s3,
    nextstrain_dot_org as __nextstrain_dot_org,
)


# While PEP-0544 allows for modules to serve as implementations of Protocols¹,
# Mypy doesn't currently support it².  Pyright does³, however, so we tell Mypy
# to "trust us", but let Pyright actually check our work.  Mypy considers the
# MYPY variable to always be True when evaluating the code, regardless of the
# assignment below.
#
# This bit of type checking chicanery is not ideal, but the benefit of having
# our module interfaces actually checked by Pyright is worth it.  In the
# future, we should maybe ditch Mypy in favor of Pyright alone, but I didn't
# want to put in the due diligence for a full switchover right now.
#
#   -trs, 12 August 2021
#
# ¹ https://www.python.org/dev/peps/pep-0544/#modules-as-implementations-of-protocols
# ² https://github.com/python/mypy/issues/5018
# ³ https://github.com/microsoft/pyright/issues/1341
#
MYPY = False
if TYPE_CHECKING and MYPY:
    s3 = cast(RemoteModule, __s3)
    nextstrain_dot_org = cast(RemoteModule, __nextstrain_dot_org)
else:
    s3 = __s3
    nextstrain_dot_org = __nextstrain_dot_org


class UnsupportedRemoteError(UserError):
    def __init__(self, path):
        super().__init__(f"""
            Unsupported remote source/destination: {path!r}

            Supported remotes are:

              - nextstrain.org/…
              - s3://…
            """)


def parse_remote_path(path: str) -> Tuple[RemoteModule, ParseResult]:
    url = urlparse(path)

    if not url.scheme or url.scheme in {"https", "http"}:
        if not url.scheme:
            if url.path.startswith("groups/"):
                # Special-case groups/… as a shortcut
                url = urlparse("https://nextstrain.org/" + path)
            else:
                # Re-parse with an assumed scheme to split .netloc from .path
                url = urlparse("https://" + path)

        if url.netloc.lower() != "nextstrain.org":
            raise UnsupportedRemoteError(path)

        return nextstrain_dot_org, url

    elif url.scheme == "s3":
        return s3, url

    else:
        raise UnsupportedRemoteError(path)

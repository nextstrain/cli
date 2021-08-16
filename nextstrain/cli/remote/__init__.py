"""
Remote destinations and sources for Nextstrain datasets and narratives.
"""

from pathlib import Path
from typing import cast, Dict, Iterable, List, Tuple, TYPE_CHECKING
from urllib.parse import urlparse, ParseResult
from ..errors import UserError
from ..types import RemoteModule
from . import s3 as __s3


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
else:
    s3 = __s3


SUPPORTED_SCHEMES: Dict[str, RemoteModule] = {
    "s3": s3,
}


def parse_remote_path(path: str) -> Tuple[RemoteModule, ParseResult]:
    url = urlparse(path)

    if url.scheme not in SUPPORTED_SCHEMES:
        raise UserError(f"""
            Unsupported remote scheme {url.scheme}://

            Supported schemes are: {", ".join(SUPPORTED_SCHEMES)}
            """)

    remote = SUPPORTED_SCHEMES[url.scheme]

    return remote, url

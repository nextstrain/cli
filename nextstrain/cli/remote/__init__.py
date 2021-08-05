"""
Remote destinations and sources for Nextstrain datasets and narratives.
"""

from types import ModuleType
from typing import Tuple
from urllib.parse import urlparse, ParseResult
from ..errors import UserError
from . import s3


SUPPORTED_SCHEMES = {
    "s3": s3,
}


def parse_remote_path(path: str) -> Tuple[ModuleType, ParseResult]:
    url = urlparse(path)

    if url.scheme not in SUPPORTED_SCHEMES:
        raise UserError(f"""
            Unsupported remote scheme {url.scheme}://

            Supported schemes are: {", ".join(SUPPORTED_SCHEMES)}
            """)

    remote = SUPPORTED_SCHEMES[url.scheme]

    return remote, url

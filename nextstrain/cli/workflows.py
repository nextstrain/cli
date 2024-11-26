"""
Pathogen workflows.
"""
import re
from typing import Optional, Tuple

from . import config
from .url import URL


def pathogen_version(spec: str) -> ...:
    # XXX FIXME: docstring
    """
    XXX FIXME

    General syntax is ``<name>@<version>``.

    ``<name>`` may not contain slashes.  It is a local name, assigned at
    ``nextstrain setup`` time.

    ``<version>`` is local name too, but often reflects upstream version name.

    ``<version>`` may be a:

        - Git ref, if <name> is a Nextstrain-maintained pathogen (i.e. not a
          third-party pathogen using that name).

    - A ``https://`` URL to a ZIP file

    ``<name>`` without ``<version>`` means:

      - "latest (stable?) version" for ``setup``
      - "local default version" for ``run``
      - "change to latest (stable?) version" for ``update``
    """
    name, version, url = parse_pathogen_version_url(spec)

    if "/" in name:
        # XXX FIXME
        raise UserError(f"""
            ...
            """)

    if not version:
        ...

    
def parse_pathogen_version(spec: str, infer: bool = True) -> Tuple[str, Optional[str], Optional[URL]]:
    # XXX FIXME: docstring
    """
    XXX FIXME
    """
    if "=" in name_version_url:
        name_version, url = name_version_url.split("=", 1)
    else:
        name_version, url = name_version_url, ""

    if "@" in name_version:
        name, version = name_version.split("@", 1)
    else:
        name, version = name_version, ""

    name    = name.strip()    or None
    version = version.strip() or None
    url     = url.strip()     or None

    if not name:
        raise UserError(f"""
            No name specified in {name_version_url!r}.

            All pathogen setups must be assigned a name, e.g. as in NAME[@VERSION][=URL].
            """)

    if version:
        # XXX FIXME
        ...

    if not url and infer:
        ...

    url = URL(url)

    if url.scheme != "https":
        raise UserError(f"""
            URL scheme is {url.scheme!r}, not {"https"!r}.

            Pathogen setup source must be an https:// URL.
            """)

    return name, version, url


def default_pathogen_version(name: str) -> Optional[str]:
    # XXX FIXME
    """
    TKTK

    >>> default_pathogen_version("measles")
    'main'

    >>> default_pathogen_version("bogus") is None
    True
    """
    return config.get(_pathogen_config_section(name), "default_version")


def _pathogen_config_section(name: str) -> str:
    assert name
    return f"pathogen {name}"

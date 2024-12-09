"""
Pathogen workflows.
"""
import re
from pathlib import Path
from typing import List, Optional, Tuple

from . import config
from .errors import UserError
from .paths import WORKFLOWS
from .url import URL
from .util import parse_version


# XXX FIXME: document these incomplete working notes properly somewhere
"""
``<name>`` without ``<version>`` means:

  - "latest (stable?) version" for ``setup``
    - if default exists, then nothing to do unless we have -f
    - if 
  - "local default version" for ``run``
    - use_default, must_exist
  - "change to latest (stable?) version" for ``update``
    - gather for pruning with use_default, setup new with use_default=False and must_exist=False
"""


class PathogenWorkflows:
    name: str
    version: str
    url: URL


    def __init__(self, name_version_url: str, new_setup: bool = False):
        name, version, url = self._parse_spec(name_version_url)

        if not name:
            raise UserError(f"""
                No name specified in {name_version_url!r}.

                All pathogen setups must be given a name, e.g. as in NAME[@VERSION[=URL]].
                """)

        if disallowed := set("/@") & set(name):
            raise UserError(f"""
                Disallowed character(s) {disallowed!r} in name {name!r}.
                """)

        if url and not new_setup:
            raise UserError(f"""
                Source URL specified in {name_version_url!r}.

                Pathogen source URLs may only be specified for `nextstrain setup`.
                """)

        if url and not version:
            raise UserError(f"""
                Source URL specified without version in {name_version_url!r}.

                A version must be specified when a source URL is specified,
                e.g. as in NAME@VERSION=URL.
                """)

        if not version:
            if new_setup:
                version = pathogen_latest_version(name)
            else:
                version = pathogen_default_version(name)

        if not version:
            raise UserError(f"""
                No version specified in {name_version_url!r}.

                There's no default version set, so a version must be specified,
                e.g. as in NAME@VERSION[=URL].
                """)

        if not url and ...:
            # XXX FIXME
            ...

        if not url:
            raise UserError(f"""
                No source URL specified in {name_version_url!r}.

                A default can not be determined, so a source URL must be
                specified explicitly, e.g. as in NAME@VERSION=URL.
                """)

        url = URL(url)

        if url.scheme != "https":
            raise UserError(f"""
                Source URL scheme is {url.scheme!r}, not {"https"!r}.

                Pathogen setup source must be an https:// URL.
                """)

        self.name    = name
        self.version = version
        self.url     = url


    @staticmethod
    def _parse_spec(name_version_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # XXX FIXME: docstring
        """
        XXX FIXME

        >>> PathogenWorkflows._parse_spec("measles")
        ('measles', None, None)

        >>> PathogenWorkflows._parse_spec("measles@v2")
        ('measles', 'v2', None)

        >>> PathogenWorkflows._parse_spec("measles@v2 = https://example.com/a.zip")
        ('measles', 'v2', 'https://example.com/a.zip')

        >>> PathogenWorkflows._parse_spec("measles = https://example.com/x.zip")
        ('measles', None, 'https://example.com/x.zip')

        >>> PathogenWorkflows._parse_spec("measles@123@abc")
        ('measles', '123@abc', None)

        >>> PathogenWorkflows._parse_spec("@xyz")
        (None, 'xyz', None)

        >>> PathogenWorkflows._parse_spec("=https://example.com")
        (None, None, 'https://example.com')

        >>> PathogenWorkflows._parse_spec("")
        (None, None, None)
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

        return name, version, url


    def workflow_path(self, workflow: str) -> Path:
        return self.path / workflow


    @property
    def path(self) -> Path:
        assert self.name
        assert self.version
        return WORKFLOWS / self.name / self.version

    
def pathogen_default_version(name: str) -> Optional[str]:
    # XXX FIXME
    """
    TKTK

    >>> pathogen_default_version("measles")
    'main'

    >>> pathogen_default_version("with-implicit-default")
    '1.2.3'

    >>> pathogen_default_version("with-no-implicit-default") is None
    True

    >>> pathogen_default_version("bogus") is None
    True
    """
    default = config.get(_pathogen_config_section(name), "default_version")

    if not default:
        versions = pathogen_versions(name)

        if len(versions) == 1:
            default = versions[0]

    return default or None


def _pathogen_config_section(name: str) -> str:
    assert name
    return f"pathogen {name}"


def pathogen_versions(name: str) -> List[str]:
    # XXX FIXME
    """
    TKTK

    >>> pathogen_versions("with-implicit-default")
    ['1.2.3']

    >>> pathogen_versions("with-no-implicit-default")
    ['4.5.6', '1.2.3']

    >>> pathogen_versions("bogus")
    []
    """
    try:
        versions = [
            d.name
                for d in (WORKFLOWS / name).iterdir()
                 if d.is_dir() ]
    except FileNotFoundError:
        versions = []

    return sorted(versions, key = parse_version, reverse = True)

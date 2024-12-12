"""
Pathogen workflows.
"""
import os.path
import re
import requests
from base64 import urlsafe_b64encode, urlsafe_b64decode
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import quote as urlquote

from . import config
from .errors import UserError
from .paths import WORKFLOWS
from .types import RunnerSetupStatus, RunnerTestResults, RunnerUpdateStatus
from .url import URL
from .util import parse_version


class PathogenWorkflows:
    name: str
    version: str
    url: URL


    def __init__(self, name_version_url: str, new_setup: bool = False):
        name, version, url = self._parse_spec(name_version_url)

        # XXX FIXME: do all this validation in _parse_spec instead?

        if not name:
            raise UserError(f"""
                No name specified in {name_version_url!r}.

                All pathogen setups must be given a name, e.g. as in NAME[@VERSION[=URL]].
                """)

        if disallowed := set([os.path.sep, os.path.altsep]) & set(name):
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

        # Valid forms:
        #   <name>
        #   <name>@<version>
        #   <name>@<version>=<url>
        assert (name and not version and not url) \
            or (name and     version and not url) \
            or (name and     version and     url)

        if not version:
            if new_setup:
                version = github_repo_latest_ref(f"nextstrain/{name}")
            else:
                version = pathogen_default_version(name)

        if not version:
            raise UserError(f"""
                No version specified in {name_version_url!r}.

                There's no default version set (or intuitable), so a version
                must be specified, e.g. as in NAME@VERSION[=URL].
                """)

        # XXX FIXME: drop this validation if we're base64ing
        if os.path.pardir in PurePath(version).parts:
            raise UserError(f"""
                Disallowed character sequence {os.path.pardir!r} combined with {os.path.sep!r} or {os.path.altsep!r} in version {version!r}.
                """)

        if not url:
            url = github_repo_ref_zipball_url(f"nextstrain/{name}", version)

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

        assert self.name
        assert self.version
        assert self.url


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

        assert name is None    or not set("@=") & set(name)
        assert version is None or not set("=")  & set(version)

        return name, version, url



    def workflow_path(self, workflow: str) -> Path:
        return self.path / workflow

    @property
    def path(self) -> Path:
        # XXX FIXME update comment if we're base64ing
        # Because we allow slashes in the version, we avoid conflicts between
        # different versions by 1) not using nested directories, e.g. WORKFLOWS /
        # self.name / self.version, 2) delimiting the version within the
        # directory name, e.g. with @ and =, and 3) restricting characters in
        # name (no path separators) and version (no parent directory traversal
        # parts).
        #   -trs, 11 Dec 2024
        assert self.name
        assert self.version
        return WORKFLOWS / self.name / self._encode_version_dir(self.version)

    @staticmethod
    def _encode_version_dir(version: str) -> str:
        # Prefixing a munged version is solely for the benefit of humans
        # looking at their filesystem.
        version_munged = re.sub(r'[^A-Za-z0-9_.-]', '-', version)
        version_b32 = b32encode(version.encode("utf-8"))
        return version_munged + "=" + version_b32

    @staticmethod
    def _decode_version_dir(name: str) -> str:
        _, version_b32 = name.split("=", 1)
        return b32decode(version_b32, casefold = True).decode("utf-8")


    def setup(dry_run: bool = False, force: bool = False) -> RunnerSetupStatus:
        ...


    def test_setup(self) -> RunnerTestResults:
        ...


    def set_default_config(self) -> None:
        ...


    def update() -> RunnerUpdateStatus:
        raise NotImplementedError


    def versions() -> Iterable[str]:
        raise NotImplementedError


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
            PathogenWorkflows._decode_version_dir(d.name)
                for d in (WORKFLOWS / name).iterdir()
                 if d.is_dir() ]
    except FileNotFoundError:
        versions = []

    return sorted(versions, key = parse_version, reverse = True)

    
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

    # XXX FIXME: reconsider this?
    if not default:
        versions = pathogen_versions(name)

        if len(versions) == 1:
            default = versions[0]

    return default or None


def _pathogen_config_section(name: str) -> str:
    assert name
    return f"pathogen {name}"


def github_repo_latest_ref(repo: str) -> str:
    # XXX FIXME
    """
    TKTK
    """
    with requests.Session() as http:
        # XXX TODO: tktk pagination
        response = http.get(f"https://api.github.com/repos/{urlquote(repo)}/tags?per_page=100")
        response.raise_for_status()

        if tags := sorted(response.json(), key = parse_version, reverse = True):
            return tags[0]

        response = http.get(f"https://api.github.com/repos/{urlquote(repo)}")
        response.raise_for_status()

        return response.json().get("default_branch")


def github_repo_ref_zipball_url(repo: str, ref: str) -> str:
    return f"https://api.github.com/repos/{urlquote(repo)}/zipball/{urlquote(ref)}"

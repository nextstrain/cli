"""
Pathogen workflows.
"""
import os.path
import re
import requests
import traceback
import yaml
from base64 import b32encode, b32decode
from tempfile import TemporaryFile
from textwrap import indent
from pathlib import Path, PurePath
from shlex import quote as shquote
from shutil import copyfileobj, rmtree
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple
from urllib.parse import quote as urlquote
from zipfile import ZipFile

from . import config
from .debug import DEBUGGING, debug
from .errors import UserError
from .paths import WORKFLOWS
from .types import SetupStatus, SetupTestResults, SetupTestResult, UpdateStatus
from .url import URL
from .util import parse_version


class PathogenSpec(NamedTuple):
    # XXX FIXME: docstring
    """
    XXX FIXME
    """
    name: Optional[str]
    version: Optional[str]
    url: Optional[URL]

    @staticmethod
    def parse(name_version_url: str) -> 'PathogenSpec':
        # XXX FIXME: docstring
        """
        XXX FIXME

        >>> PathogenSpec.parse("measles")
        PathogenSpec(name='measles', version=None, url=None)

        >>> PathogenSpec.parse("measles@v2")
        PathogenSpec(name='measles', version='v2', url=None)

        >>> PathogenSpec.parse("measles@v2 = https://example.com/a.zip")
        PathogenSpec(name='measles', version='v2', url=URL(scheme='https', netloc='example.com', path='/a.zip', query='', fragment=''))

        >>> PathogenSpec.parse("measles = https://example.com/x.zip")
        PathogenSpec(name='measles', version=None, url=URL(scheme='https', netloc='example.com', path='/x.zip', query='', fragment=''))

        >>> PathogenSpec.parse("measles@123@abc")
        PathogenSpec(name='measles', version='123@abc', url=None)

        >>> PathogenSpec.parse("@xyz")
        PathogenSpec(name=None, version='xyz', url=None)

        >>> PathogenSpec.parse("=https://example.com")
        PathogenSpec(name=None, version=None, url=URL(scheme='https', netloc='example.com', path='', query='', fragment=''))

        >>> PathogenSpec.parse("")
        PathogenSpec(name=None, version=None, url=None)
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

        if url is not None:
            url = URL(url)

        return PathogenSpec(name, version, url)


class PathogenWorkflows:
    # XXX FIXME docstring
    """
    TKTK
    """
    name: str
    version: str
    url: Optional[URL]


    def __init__(self, name_version_url: str, new_setup: bool = False):
        # XXX FIXME docstring
        """
        TKTK
        """
        name, version, url = PathogenSpec.parse(name_version_url)

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
                URL specified in {name_version_url!r}.

                Pathogen setup URLs may only be specified for `nextstrain setup`.
                """)

        if url and not version:
            raise UserError(f"""
                URL specified without version in {name_version_url!r}.

                A version must be specified when a setup URL is specified,
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
                version = pathogen_default_version(name, implicit = True)

        if not version:
            if new_setup:
                raise UserError(f"""
                    No version specified in {name_version_url!r}.

                    There's no default version intuitable, so a version must be
                    specified, e.g. as in NAME@VERSION.
                    """)
            else:
                raise UserError(f"""
                    No version specified in {name_version_url!r}.

                    There's no default version set (or intuitable), so a version
                    must be specified, e.g. as in NAME@VERSION.

                    Existing versions of {name!r} you have set up are:

                    {{versions}}

                    Hint: You can set a default version for {name!r} by running:

                        nextstrain setup --set-default {shquote(name)}@VERSION

                    """, versions = indent("\n".join(pathogen_versions(name)), "    "))

        if new_setup:
            if not url:
                url = github_repo_ref_zipball_url(f"nextstrain/{name}", version)

            if not url:
                raise UserError(f"""
                    No setup URL specified in {name_version_url!r}.

                    A default can not be determined, so a setup URL must be
                    specified explicitly, e.g. as in NAME@VERSION=URL.
                    """)

            if url.scheme != "https":
                raise UserError(f"""
                    URL scheme is {url.scheme!r}, not {"https"!r}.

                    Pathogen setup URLs must be https://.
                    """)

        self.name    = name
        self.version = version
        self.url     = url

        assert self.name
        assert self.version


    def __str__(self) -> str:
        return f"{self.name}@{self.version}"


    def __eq__(self, other) -> bool:
        if self.__class__ != other.__class__:
            return False

        return self.name    == other.name \
           and self.version == other.version \
           and (self.url    == other.url or self.url is None or other.url is None)


    @property
    def registration_path(self) -> Path:
        return self.path / "nextstrain-pathogen.yaml"

    def workflow_path(self, workflow: str) -> Path:
        return self.path / workflow

    @property
    def path(self) -> Path:
        assert self.name
        assert self.version
        return WORKFLOWS / self.name / self._encode_version_dir(self.version)

    @staticmethod
    def _encode_version_dir(version: str) -> str:
        """
        >>> PathogenWorkflows._encode_version_dir("1.2.3")
        '1.2.3=GEXDELRT'

        >>> PathogenWorkflows._encode_version_dir("abc/lmnop/xyz")
        'abc-lmnop-xyz=MFRGGL3MNVXG64BPPB4XU==='
        """
        # Prefixing a munged version is solely for the benefit of humans
        # looking at their filesystem.
        version_munged = re.sub(r'[^A-Za-z0-9_.-]', '-', version)
        version_b32 = b32encode(version.encode("utf-8")).decode("utf-8")
        assert "=" not in version_munged
        return version_munged + "=" + version_b32

    @staticmethod
    def _decode_version_dir(fname: str) -> str:
        """
        >>> PathogenWorkflows._decode_version_dir(PathogenWorkflows._encode_version_dir("v42"))
        'v42'

        >>> PathogenWorkflows._decode_version_dir("1.2.3=GEXDELRT")
        '1.2.3'

        Munged version prefix for humans is ignored.

        >>> PathogenWorkflows._decode_version_dir("x.y.z=GEXDELRT")
        '1.2.3'
        >>> PathogenWorkflows._decode_version_dir("=GEXDELRT")
        '1.2.3'

        Case-mangled names are still ok.

        >>> PathogenWorkflows._decode_version_dir("1.2.3=gExDeLrT")
        '1.2.3'
        """
        _, version_b32 = fname.split("=", 1)
        return b32decode(version_b32, casefold = True).decode("utf-8")


    def setup(self, dry_run: bool = False, force: bool = False) -> SetupStatus:
        assert self.url

        # XXX FIXME: dry_run
        # XXX FIXME: force
        if not force and self.path.exists():
            print(f"Using existing set up in {str(self.path)!r}.")
            print(f"  Hint: if you want to ignore this existing installation, re-run `nextstrain setup` with --force.")
            return True

        if self.path.exists():
            print(f"Removing existing directory {str(self.path)!r} to start fresh…")
            if not dry_run:
                rmtree(str(self.path))

        try:
            response = requests.get(self.url, stream = True)
            response.raise_for_status()

        except requests.exceptions.ConnectionError as err:
            raise UserError(f"""
                Could not connect to {self.url.netloc!r} to download
                pathogen for setup:

                    {type(err).__name__}: {err}

                The URL may be invalid or you may be experiencing network
                connectivity issues.
                """) from err

        except requests.exceptions.HTTPError as err:
            def redirect_list(response, initial_indent = "    ", redirect_indent = "  ⮡ ") -> str:
                return "\n".join(
                    initial_indent + (redirect_indent * i) + r.url
                        for i, r in enumerate([*response.history, response]) )

            if 400 <= err.response.status_code <= 499:
                raise UserError(f"""
                    Failed to download pathogen setup URL:

                    {{urls}}

                    The server responded with an error:

                        {type(err).__name__}: {err}

                    The URL may be incorrect (e.g. misspelled) or no longer
                    accessible.
                    """, urls = redirect_list(err.response)) from err

            elif 500 <= err.response.status_code <= 599:
                raise UserError(f"""
                    Failed to download pathogen setup URL:

                    {{urls}}

                    The server responded with an error:

                        {type(err).__name__}: {err}

                    This may be a permanent error or a temporary failure, so it
                    may be worth waiting a little bit and trying again a few
                    more times.
                    """, urls = redirect_list(err.response)) from err


        content_type = response.headers["Content-Type"]

        if content_type != "application/zip":
            raise UserError(f"""
                Unexpected Content-Type for {self.url!r}: {content_type!r}

                Expected 'application/zip', i.e. a ZIP file (.zip).
                """)

        # Write remote ZIP file to a temporary local file so its seekable…
        with TemporaryFile("w+b") as zipfh:
            copyfileobj(response.raw, zipfh)

            # …and extract its contents.
            with ZipFile(zipfh) as zipfile:
                safe_members = [
                    (filename, member)
                        for filename, member
                         in ((PurePath(m.filename), m) for m in zipfile.infolist())
                         if not filename.is_absolute()
                        and os.path.pardir not in filename.parts ]

                try:
                    prefix = PurePath(os.path.commonpath([filename for filename, member in safe_members]))
                except ValueError:
                    prefix = PurePath("")

                if not dry_run:
                    self.path.mkdir(parents = True)

                for filename, member in safe_members:
                    if filename == prefix:
                        continue

                    member.filename = str(filename.relative_to(prefix)) \
                                    + (os.path.sep if member.is_dir() else '')

                    if not dry_run:
                        debug(zipfile.extract(member, self.path))
                    else:
                        debug(member.filename)

                print(f"Extracted {len(safe_members):,} files and directories to {str(self.path)!r}.")

        return True


    def test_setup(self) -> SetupTestResults:
        def test_compatibility() -> SetupTestResult:
            msg = "nextstrain-pathogen.yaml declares `nextstrain run` compatibility"

            try:
                registration = read_pathogen_registration(self.registration_path)
            except (OSError, yaml.YAMLError, ValueError):
                if DEBUGGING:
                    traceback.print_exc()
                return msg + "\n(couldn't read registration)", False

            try:
                compatibility = registration["compatibility"]["nextstrain run"]
            except (KeyError, IndexError, TypeError) as err:
                return msg + "\n(couldn't find 'compatibility: nextstrain run: …' field)", False

            return msg, bool(compatibility)

        return [
            ('downloaded',
                self.path.exists()),

            ('contains nextstrain-pathogen.yaml',
                self.registration_path.is_file()),

            test_compatibility(),
        ]


    def set_default_config(self) -> None:
        raise NotImplementedError


    def update(self) -> UpdateStatus:
        raise NotImplementedError


    def versions(self) -> Iterable[str]:
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

    
def pathogen_default_version(name: str, implicit: bool = True) -> Optional[str]:
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
    assert name
    default = config.get(f"pathogen {name}", "default_version")

    # XXX FIXME: reconsider this?
    if not default and implicit:
        versions = pathogen_versions(name)

        if len(versions) == 1:
            default = versions[0]

    return default or None


def read_pathogen_registration(path: Path) -> Dict:
    with path.open("r", encoding = "utf-8") as f:
        registration = yaml.safe_load(f)

    # XXX TODO: Consider doing actual schema validation here in the future.
    #   -trs, 12 Dec 2024
    if not isinstance(registration, dict):
        raise ValueError(f"pathogen registration not a dict (got a {type(registration).__name__}): {str(path)!r}")

    return registration


def github_repo_latest_ref(repo: str) -> Optional[str]:
    # XXX FIXME
    """
    TKTK
    """
    with requests.Session() as http:
        repo = http.get(f"https://api.github.com/repos/{urlquote(repo)}")

        if repo.status_code == 404:
            return None
        else:
            repo.raise_for_status()

        repo = repo.json()

        # XXX TODO: tktk pagination
        tags_url = URL(repo["tags_url"])
        tags = http.get(tags_url._replace(query = "per_page=100&" + tags_url.query))
        tags.raise_for_status()

        if tags := sorted(tags.json(), key = parse_version, reverse = True):
            return tags[0]

        return repo["default_branch"]


def github_repo_ref_zipball_url(repo: str, ref: str) -> URL:
    return URL(f"https://api.github.com/repos/{urlquote(repo)}/zipball/{urlquote(ref)}")

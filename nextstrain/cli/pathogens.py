"""
Pathogen workflows.
"""
import json
import jsonschema
import os
import os.path
import re
import traceback
import yaml
from base64 import b32encode, b32decode, b64decode
from inspect import cleandoc
from itertools import groupby
from tempfile import TemporaryFile
from textwrap import indent
from os import chmod, stat
from pathlib import Path, PurePath
from shlex import quote as shquote
from shutil import copyfileobj, rmtree
from stat import S_IXUSR, S_IXGRP, S_IXOTH, S_IRGRP, S_IROTH
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple
from urllib.parse import quote as urlquote
from zipfile import ZipFile

from . import config
from . import requests
from . import resources
from .debug import DEBUGGING, debug
from .errors import InternalError, UserError
from .net import is_loopback
from .paths import PATHOGENS
from .types import SetupStatus, SetupTestResults, SetupTestResult, UpdateStatus
from .url import URL, NEXTSTRAIN_DOT_ORG
from .util import parse_version_lax, print_and_check_setup_tests, request_list, warn


# XXX TODO: I'm not very happy with the entirety of the conceptual organization
# and physical code organization in this file—in particular 1) the new_setup
# flag for handling of new vs. existing setups, 2) the tension between the main
# PathogenVersion class and the surrounding functions, and 3) the way the
# PathogenVersion constructor inconsistently cares about what's on the
# filesystem or not (e.g. for defaults)—but it does the job for now.  If it
# continues to feel ill-fitting for the various uses, I suspect I'll end up
# reorganizing it after a while.  This is also to say, if you're working in
# this code and have ideas for improving its organization, please do
# suggest/discuss them!
#   -trs, 15 Jan 2025


class PathogenSpec(NamedTuple):
    """
    A parsed pathogen spec of the form ``[<name>][@<version>][=<url>]``,
    represented as a named tuple.

    No validation takes place and all fields are optional.  This data structure
    represents the very first step of handling a user-provided pathogen spec.
    As such it focuses only on accurately representing what the user provided.
    Validation is left for subsequent steps, where requirements can
    appropriately vary depending on context (e.g. program entry point).
    """
    name: Optional[str]
    version: Optional[str]
    url: Optional[URL]

    def __str__(self) -> str:
        return (self.name or "") + "@" + (self.version or "") + "=" + (str(self.url) or "")

    @staticmethod
    def parse(name_version_url: str) -> 'PathogenSpec':
        """
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

        # The parsing above is wrong if these assertions don't hold
        assert name is None    or not set("@=") & set(name)
        assert version is None or not set("=")  & set(version)

        if url is not None:
            url = URL(url)

        return PathogenSpec(name, version, url)


class PathogenVersion:
    """
    A pathogen setup with a specific *name* and *version*.

    The entity used by ``nextstrain setup``, ``nextstrain update``, and
    ``nextstrain run``.
    """
    spec: PathogenSpec

    name: str
    version: str

    path: Path
    registration_path: Path
    setup_receipt_path: Path

    setup_receipt: Optional[dict] = None
    url: Optional[URL] = None
    registration: Optional[dict] = None


    def __init__(self, name_version_url: str, new_setup: bool = False):
        """
        *name_version_url* is a pathogen spec string suitable for
        :meth:`PathogenSpec.parse`.

        If *new_setup* is ``False`` (the default), then the given pathogen spec
        is required to refer to an existing pathogen setup, e.g. used by
        ``nextstrain run``.

        If *new_setup* is ``True``, then the given pathogen spec is expected to
        have :meth:`.setup` called on it, e.g. used by ``nextstrain setup``.
        """

        name, version, url = self.spec = PathogenSpec.parse(name_version_url)

        if not name:
            if new_setup:
                raise UserError(f"""
                    No name specified in {name_version_url!r}.

                    All pathogen setups must be given a name, e.g. as in NAME[@VERSION[=URL]].
                    """)
            else:
                raise UserError(f"""
                    No pathogen name specified in {name_version_url!r}.
                    """)

        if disallowed := set([os.path.sep, os.path.altsep or os.path.sep]) & set(name):
            raise UserError(f"""
                Disallowed character(s) {"".join(disallowed)!r} in name {name!r}.
                """)

        if name.lower() == "cli":
            raise UserError(f"""
                The name {name!r} is reserved for use by Nextstrain CLI itself
                in `nextstrain update cli`.
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
                version = nextstrain_repo_latest_version(name)
            else:
                version = default_version_of(name, implicit = True)

        if not version:
            if new_setup:
                raise UserError(f"""
                    No version specified in {name_version_url!r}.

                    There's no default version intuitable, so a version must be
                    specified, e.g. as in NAME@VERSION.
                    """)
            else:
                # XXX TODO: This error case should maybe be handled outside of
                # the constructor, with the constructor modified to raise a
                # more generic FileNotFoundError instead.
                #   -trs, 3 Feb 2025
                if versions := versions_of(name):
                    raise UserError(f"""
                        No version specified in {name_version_url!r}.

                        There's no default version set (or intuitable), so a version
                        must be specified, e.g. as in NAME@VERSION.

                        Existing versions of {name!r} you have set up are:

                        {{versions}}

                        Hint: You can set a default version for {name!r} by running:

                            nextstrain setup --set-default {shquote(name)}@VERSION

                        if you don't want to specify an explicit version every time.
                        """, versions = indent("\n".join(f"{name}@{v}" for v in versions), "    "))
                else:
                    raise UserError(f"""
                        No pathogen setup exists for {name_version_url!r}.

                        Did you set it up yet?

                        Hint: to set it up, run `nextstrain setup {shquote(name_version_url)}`.
                        """)

        self.name    = name
        self.version = version

        assert self.name
        assert self.version

        self.path = PATHOGENS / self.name / PathogenVersion.encode_version_dir(self.version)

        self.registration_path  = self.path / "nextstrain-pathogen.yaml"
        self.setup_receipt_path = self.path.with_suffix(self.path.suffix + ".json")

        try:
            self.registration = read_pathogen_registration(self.registration_path)
        except RegistrationError:
            # Ignore malformed registrations during __init__() here to avoid a
            # noisy constructor for PathogenVersion.  We're more noisy about
            # registration issues in setup(), which will be seen during the
            # initial `nextstrain setup` or subsequent `nextstrain update`.
            self.registration = None

        if not new_setup:
            if not self.path.is_dir():
                # XXX TODO: This error case should maybe be handled outside of
                # the constructor, with the constructor modified to raise a
                # more generic FileNotFoundError instead.
                #   -trs, 3 Feb 2025
                if versions := versions_of(name):
                    raise UserError(f"""
                        No pathogen setup exists for {name_version_url!r}{f" in {str(self.path)!r}" if DEBUGGING else ""}.

                        Existing versions of {name!r} you have set up are:

                        {{versions}}

                        Did you mean one of those?
                        """, versions = indent("\n".join(f"{name}@{v}" for v in versions), "    "))
                else:
                    raise UserError(f"""
                        No pathogen setup exists for {name_version_url!r}{f" in {str(self.path)!r}" if DEBUGGING else ""}.

                        Did you set it up yet?

                        Hint: to set it up, run `nextstrain setup {shquote(name_version_url)}`.
                        """)

            try:
                with self.setup_receipt_path.open(encoding = "utf-8") as f:
                    self.setup_receipt = json.load(f)
                    assert isinstance(self.setup_receipt, dict)
            except FileNotFoundError:
                pass

            if not url and self.setup_receipt:
                if url := self.setup_receipt.get("url"):
                    url = URL(url)

        if new_setup:
            if not url:
                url = nextstrain_repo_zip_url(name, version)

            if not url:
                raise UserError(f"""
                    No setup URL specified in {name_version_url!r}.

                    A default URL can not be determined, so a setup URL must be
                    specified explicitly, e.g. as in NAME@VERSION=URL.
                    """)

            if url.scheme != "https" and not (is_loopback(url.hostname) and url.scheme == "http"):
                raise UserError(f"""
                    URL scheme is {url.scheme!r}, not {"https"!r}.

                    Pathogen setup URLs must be https://.
                    """)

        self.url = url


    def registered_workflows(self) -> Dict[str, Dict]:
        """
        Parses :attr:`.registration` to return a dict of registered workflows,
        where the keys are workflow names.
        """
        if self.registration is None:
            debug("pathogen does not have a registration")
            return {}

        workflows = self.registration.get("workflows")
        if not isinstance(workflows, dict):
            debug(f"pathogen registration.workflows is not a dict (got a {type(workflows).__name__})")
            return {}

        return workflows


    def compatible_workflows(self, feature: str) -> Dict[str, Dict]:
        """
        Filters registered workflows to return a subset of workflows that are
        compatible with the provided *feature*.
        """
        return {
            name: info
            for name, info in self.registered_workflows().items()
            if isinstance(info, dict) and info.get("compatibility", {}).get(feature)
        }


    def workflow_registration(self, name: str) -> Optional[dict]:
        """
        Returns the registration dictionary for the workflow *name*.

        Returns ``None`` if the workflow is not registered, does not have
        registration information, or the registered information is not a
        dictionary.
        """
        if (info := self.registered_workflows().get(name)) and not isinstance(info, dict):
            debug(f"pathogen registration.workflows[{name!r}] is not a dict (got a {type(info).__name__})")
            return None

        return info


    def workflow_path(self, name: str) -> Path:
        if (info := self.workflow_registration(name)) and (path := info.get("path")):
            debug(f"pathogen registration specifies {path!r} for workflow {name!r}")

            # Forbid anchored paths in registration info, as it's never correct
            # practice.  An anchored path is just an absolute path on POSIX
            # systems but covers more "absolute-like" cases on Windows systems
            # too.
            if PurePath(path).anchor:
                raise UserError(f"""
                    The {self.registration_path.name} file for {str(self)!r}
                    registers an anchored path for the workflow {name!r}:

                        {path}

                    Registered workflow paths must be relative to (and within)
                    the pathogen source itself.  This is a mistake that the
                    pathogen author(s) must fix.
                    """)

            # Ensure the relative path resolves _within_ the pathogen repo to
            # avoid shenanigans.
            resolved_pathogen_path = self.path.resolve()
            resolved_workflow_path = (resolved_pathogen_path / path).resolve()

            if not resolved_workflow_path.is_relative_to(resolved_pathogen_path):
                raise UserError(f"""
                    The {self.registration_path.name} file for {str(self)!r}
                    registers an out-of-bounds path for the workflow {name!r}:

                        {path}

                    which resolves to:

                        {str(resolved_workflow_path)}

                    which is outside of the pathogen's source.

                    Registered workflow paths must be within the pathogen
                    source itself.  This is a mistake that the pathogen
                    author(s) must fix.
                    """)

            debug(f"resolved workflow {name!r} to {str(resolved_workflow_path)!r}")
            return resolved_workflow_path

        debug(f"pathogen registration does not specify path for workflow {name!r}; using name as path")
        return self.path / name


    def setup(self, dry_run: bool = False, force: bool = False) -> SetupStatus:
        """
        Downloads and installs this pathogen version from :attr:`.url`.
        """
        assert self.url

        if not force and self.path.exists():
            print(f"Using existing setup in {str(self.path)!r}.")
            print(f"  Hint: if you want to ignore this existing setup, re-run `nextstrain setup` with --force.")
            return True

        if self.path.exists():
            assert force
            print(f"Removing existing setup {str(self.path)!r} to start fresh…")
            if not dry_run:
                rmtree(str(self.path))
                self.setup_receipt_path.unlink(missing_ok = True)

        try:
            # Heads up: if you add explicit authn to this request—either an
            # "auth" parameter or an "Authorization" header—consider if it
            # breaks the assumption of netrc-based auth in the 401/403 error
            # handling below and make changes as necessary.  Thanks!
            #   -trs, 25 Sept 2025
            response = requests.get(str(self.url), headers = {"Accept": "application/zip, */*"}, stream = True)
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
            if 400 <= err.response.status_code <= 499:
                if (err.response.status_code in {401, 403}
                and (auth := err.response.request.headers["Authorization"])
                and auth.startswith("Basic ")):
                    user = b64decode(auth.split(" ", 1)[1]).decode("utf-8").split(":", 1)[0]

                    # Logic here matches requests.utils.get_netrc_auth()
                    if "NETRC" in os.environ:
                        netrcs = [os.environ["NETRC"]]
                    else:
                        netrcs = ["~/.netrc", "~/_netrc"]

                    if netrc := next(filter(os.path.exists, map(os.path.expanduser, netrcs)), None):
                        # We could also check that the netrc file we just found
                        # contains the credentials we see in the request… but
                        # that feels slightly excessive.
                        #   -trs, 25 Sept 2025
                        hint = cleandoc(f"""
                            Authentication credentials for user

                                {user}

                            stored in the netrc file

                                {netrc}

                            were automatically used.  Perhaps they're invalid?

                            You may wish to retry without using stored credentials,
                            either by removing them from your netrc file or setting
                            the NETRC environment variable to an empty value.
                            """)
                    else:
                        hint = cleandoc(f"""
                            Authentication credentials for user

                                {user}

                            potentially stored in one of the following netrc files

                                {'''
                                '''.join(netrcs)}

                            were automatically used.  Perhaps they're invalid?

                            You may wish to retry without using stored credentials,
                            either by removing them from one of the netrc files
                            or setting the NETRC environment variable to an
                            empty value.
                            """)
                else:
                    hint = cleandoc(f"""
                        The URL may be incorrect (e.g. misspelled) or no longer
                        accessible.
                        """)

                raise UserError(f"""
                    Failed to download pathogen setup URL:

                    {{urls}}

                    The server responded with an error:

                        {type(err).__name__}: {err}

                    {{hint}}
                    """, urls = request_list(err.response), hint = hint) from err

            elif 500 <= err.response.status_code <= 599:
                raise UserError(f"""
                    Failed to download pathogen setup URL:

                    {{urls}}

                    The server responded with an error:

                        {type(err).__name__}: {err}

                    This may be a permanent error or a temporary failure, so it
                    may be worth waiting a little bit and trying again a few
                    more times.
                    """, urls = request_list(err.response)) from err

            else:
                raise err


        content_type = response.headers["Content-Type"]

        if content_type != "application/zip":
            raise UserError(f"""
                Unexpected Content-Type {content_type!r} when downloading
                pathogen setup URL:

                {{urls}}

                Expected 'application/zip', i.e. a ZIP file (.zip).
                """, urls = request_list(response))

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

                debug("common path prefix of archive members:", repr(prefix))
                debug("mkdir:", self.path)

                if not dry_run:
                    self.path.mkdir(parents = True)

                for filename, member in safe_members:
                    if filename == prefix or filename in prefix.parents:
                        continue

                    member.filename = str(filename.relative_to(prefix)) \
                                    + (os.path.sep if member.is_dir() else '')

                    debug("extracting:", member.filename)

                    if not dry_run:
                        debug("extracted:", extracted := zipfile.extract(member, self.path))

                        # Jeez.  This is making me question if we should be
                        # using tarballs here instead.
                        #   -trs, 10 Jan 2025
                        if (member.create_system == 3               # Unix, to know what to expect in external_attr
                        and (zipmode := member.external_attr >> 16) # Discard rightmost two bytes, leaving first two bytes (the file mode)
                        and zipmode & S_IXUSR):
                            oldmode = stat(extracted).st_mode
                            newmode = (
                                  oldmode
                                | S_IXUSR                                # u+x
                                | (S_IXGRP if oldmode & S_IRGRP else 0)  # g+x if g has r
                                | (S_IXOTH if oldmode & S_IROTH else 0)) # o+x if o has r
                            debug(f"chmod {oldmode:o} → {newmode:o}:", extracted)
                            chmod(extracted, newmode)

                print(f"Extracted {len(safe_members):,} files and directories to {str(self.path)!r}.")

        self.setup_receipt = {
            "name": self.name,
            "version": self.version,
            "url": str(self.url) }

        with self.setup_receipt_path.open("w", encoding = "utf-8") as f:
            json.dump(self.setup_receipt, f, indent = "  ")
            print(file = f)

        try:
            self.registration = read_pathogen_registration(self.registration_path)
        except RegistrationError as err:
            self.registration = None

            warn(cleandoc(f"""
                The {self.registration_path.name} file for {str(self)!r} is malformed:

                    {'''
                    '''.join(str(err).splitlines())}

                It will not be used and this pathogen setup may not be fully-functional.
                \
                """))
            if DEBUGGING:
                traceback.print_exc()

        return True


    def test_setup(self) -> SetupTestResults:
        def test_compatibility() -> SetupTestResult:
            msg = "nextstrain-pathogen.yaml declares `nextstrain run` compatibility"

            if self.registration is None:
                return msg + "\n(couldn't read registration)", False

            if not self.registered_workflows():
                return msg + "\n(no workflows registered)", False

            if not self.compatible_workflows("nextstrain run"):
                return msg + "\n(no workflows registered as compatible)", False

            return msg, True

        return [
            ('downloaded',
                self.path.is_dir()),

            ('contains nextstrain-pathogen.yaml',
                self.registration_path.is_file()),

            test_compatibility(),

            *((f'`nextstrain run` workflow {name!r} exists', self.workflow_path(name).is_dir())
                for name in self.compatible_workflows("nextstrain run")),
        ]


    def set_default_config(self) -> None:
        """
        Sets this version as the default for this pathogen.
        """
        config.set(f"pathogen {self.name}", "default_version", self.version)


    def update(self) -> UpdateStatus:
        """
        Updates a specific version in-place or updates the default version to
        the newest version.

        An in-place update is attempted if this :cls:`PathogenVersion` was
        instantiated with a version in the pathogen spec (i.e. not defaulted).
        This is appropriate for a version that's mutable, like a branch name.
        The process is roughly equivalent to `nextstrain setup --force NAME@VERSION`.

        Otherwise, a default version update is attempted by setting up the
        newest version and then making it the default.  This is appropriate for
        a version that's immutable, like a tag name.  The process is roughly
        equivalent to `nextstrain setup --set-default NAME`.
        """
        if self.spec.version:
            new = PathogenVersion(self.name + "@" + self.version, new_setup = True)
        else:
            new = PathogenVersion(self.name, new_setup = True)

        if new.version != self.version:
            print(f"Updating from {str(self)!r} to {str(new)!r}…")
            ok = new.setup()

        elif new.url != self.url:
            print(f"Updating {str(new)!r} in-place…")
            ok = new.setup(force = True)

        else:
            assert new == self

            if self.spec.version:
                print(f"{str(self)!r} already up-to-date.")
            else:
                print(f"{self.name!r} already at newest version.")
            print()

            return True

        # None of the update() routines for runners test their setups, but it
        # makes sense to do so for pathogens.  Here's why:
        #
        # The Docker/Singularity/AWS Batch runtime checks focus on the
        # machinery required to use the runtime image, but do not test the
        # contents/correctness of the runtime image *itself*; they assume
        # that's ok.  The pathogen checks OTOH solely test the
        # contents/correctness of the pathogen itself; so it makes sense to
        # check it after any change/update unlike the Docker checks.  The Conda
        # runtime checks do both! (and so ostensibly should run after update
        # too…)
        #   -trs, 2 April 2025
        #    see also <https://github.com/nextstrain/cli/pull/407#discussion_r1990288763>
        if ok:
            print(f"Checking setup…")
            ok = print_and_check_setup_tests(new.test_setup())

        if ok and not self.spec.version:
            print(f"Setting default version to {str(new)!r}.")
            new.set_default_config()

            # XXX TODO SOON: Delete old version (self.path) at this point?  The
            # runtimes delete old versions after update to recover disk space.
            # Pathogens use a lot less space, but I think it's still worth it
            # to tidy up?  OTOH, it seems more likely for pathogens that people
            # will blindly update to see if there's anything new and then want
            # to trial it/compare it against the old version (or immediately
            # revert back if the new version breaks something).
            #   -trs, 3 Feb 2025

        return ok


    @staticmethod
    def encode_version_dir(version: str) -> str:
        """
        >>> PathogenVersion.encode_version_dir("1.2.3")
        '1.2.3=GEXDELRT'

        >>> PathogenVersion.encode_version_dir("abc/lmnop/xyz")
        'abc-lmnop-xyz=MFRGGL3MNVXG64BPPB4XU==='
        """
        # Prefixing a munged version is solely for the benefit of humans
        # looking at their filesystem.
        version_munged = re.sub(r'[^A-Za-z0-9_.-]', '-', version)
        version_b32 = b32encode(version.encode("utf-8")).decode("utf-8")
        assert "=" not in version_munged
        return version_munged + "=" + version_b32

    @staticmethod
    def decode_version_dir(fname: str) -> str:
        """
        >>> PathogenVersion.decode_version_dir(PathogenVersion.encode_version_dir("v42"))
        'v42'

        >>> PathogenVersion.decode_version_dir("1.2.3=GEXDELRT")
        '1.2.3'

        Munged version prefix for humans is ignored.

        >>> PathogenVersion.decode_version_dir("x.y.z=GEXDELRT")
        '1.2.3'
        >>> PathogenVersion.decode_version_dir("=GEXDELRT")
        '1.2.3'

        Case-mangled names are still ok.

        >>> PathogenVersion.decode_version_dir("1.2.3=gExDeLrT")
        '1.2.3'
        """
        _, version_b32 = fname.split("=", 1)
        return b32decode(version_b32, casefold = True).decode("utf-8")


    def __str__(self) -> str:
        return f"{self.name}@{self.version}"

    def __repr__(self) -> str:
        return f"<PathogenVersion {self!s} url={self.url!r} path={str(self.path)!r}>"

    def __eq__(self, other) -> bool:
        if self.__class__ != other.__class__:
            return False

        return self.name    == other.name \
           and self.version == other.version \
           and (self.url    == other.url or self.url is None or other.url is None)


class UnmanagedPathogen:
    """
    A local directory that's a pathogen repo, not managed by Nextstrain CLI.

    Used by ``nextstrain run``.  Includes only the :cls:`PathogenVersion` API
    surface that ``nextstrain run`` requires.
    """
    path: Path
    registration_path: Path

    registration: Optional[dict] = None

    def __init__(self, path: str):
        spec = PathogenSpec.parse(path)

        if not spec.name or (spec.name not in set([os.path.curdir, os.path.pardir]) and not (set(spec.name) & set([os.path.sep, os.path.altsep or os.path.sep]))):
            raise ValueError(f"the {spec.name!r} part of {path!r} does not look like a path")

        self.path = Path(path)

        if not self.path.is_dir():
            raise UserError(f"""
                Path {str(self.path)!r} is not a directory (or does not exist).
                """)

        self.registration_path = self.path / "nextstrain-pathogen.yaml"

        try:
            self.registration = read_pathogen_registration(self.registration_path)
        except RegistrationError as err:
            self.registration = None

            warn(cleandoc(f"""
                The {self.registration_path.name} file for {str(self)!r} is malformed:

                    {'''
                    '''.join(str(err).splitlines())}

                It will not be used and this pathogen's workflows may not be fully-functional.
                \
                """))
            if DEBUGGING:
                traceback.print_exc()

    registered_workflows = PathogenVersion.registered_workflows
    compatible_workflows = PathogenVersion.compatible_workflows
    workflow_registration = PathogenVersion.workflow_registration
    workflow_path = PathogenVersion.workflow_path

    def __str__(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return f"<UnmanagedPathogen path={str(self.path)!r}>"


def every_pathogen_default_by_name(pathogens: Dict[str, Dict[str, PathogenVersion]] = None) -> Dict[str, PathogenVersion]:
    """
    Scans file system to return a dict of :cls:`PathogenVersion` objects,
    representing pathogen default version setups, keyed by their name.

    Sorted by name (case-insensitively).

    To avoid a filesystem scan for consistency (and performance in the limit)
    when it's been scanned already, the result of a previous call to
    :func:`all_pathogen_versions_by_name` may be passed.
    """
    if pathogens is None:
        pathogens = all_pathogen_versions_by_name()

    # The `default_version in versions` check avoids a KeyError in the edge
    # case of a configured default version that's not present on the
    # filesystem.
    return {
        name: versions[default_version]
            for name, versions in pathogens.items()
             if (default_version := default_version_of(name, versions = list(versions.keys())))
            and default_version in versions }


def all_pathogen_versions_by_name() -> Dict[str, Dict[str, PathogenVersion]]:
    """
    Scans file system to return a two-level dict of :cls:`PathogenVersion`
    objects, representing all pathogen version setups, keyed by their name then
    version.

    Sorted by name (case-insensitively) and version (PEP-440-compliant versions
    (newest → oldest) first then other textual versions (A → Z and 0 → 9, by
    parts)).

    >>> from pprint import pp
    >>> pp(all_pathogen_versions_by_name()) # doctest: +ELLIPSIS
    {'with-implicit-default': {'1.2.3': <PathogenVersion with-implicit-default@1.2.3 ...>},
     'with-no-implicit-default': {'4.5.6': <PathogenVersion with-no-implicit-default@4.5.6 ...>,
                                  '1.2.3': <PathogenVersion with-no-implicit-default@1.2.3 ...>}}
    """
    return {
        name: { v.version: v for v in versions }
            for name, versions
             in groupby(all_pathogen_versions(), lambda p: p.name) }


def all_pathogen_versions() -> List[PathogenVersion]:
    """
    Scans file system to return a list of :cls:`PathogenVersion` objects
    representing found setups.

    Sorted by name (case-insensitively) and version (PEP-440-compliant versions
    (newest → oldest) first then other textual versions (A → Z and 0 → 9, by
    parts)).
    """
    if not PATHOGENS.exists():
        return []

    return [
        PathogenVersion(pathogen_dir.name + "@" + version)
            for pathogen_dir in sorted(PATHOGENS.iterdir(), key = lambda p: p.name.casefold())
             if pathogen_dir.is_dir()
            for version in versions_within(pathogen_dir) ]


def pathogen_defaults(name: str) -> Tuple[Optional[PathogenVersion], Optional[PathogenVersion]]:
    """
    Returns a tuple of :cls:`PathogenVersion` objects (or ``None``)
    representing the explicitly configured default for pathogen *name* (if any)
    and the implicit default (if any).

    Most code won't care about the distinction, but ``nextstrain setup`` does.
    """
    if configured_default := default_version_of(name, implicit = False):
        # XXX TODO: Handle the edge case of a configured default version that
        # no longer exists on the filesystem.  For now, the code below will
        # raise a UserError (see also FileNotFoundError comments in
        # PathogenVersion.__init__).  Precedence for warning and ignoring
        # exists in nextstrain/cli/runner/__init__.py, FWIW.
        #   -trs, 3 Feb 2025
        #
        # See also what every_pathogen_default_by_name() does.
        #   -trs, 28 Mar 2025
        configured_default = PathogenVersion(f"{name}@{configured_default}")
    else:
        configured_default = None

    if configured_default:
        default = configured_default
    elif default := default_version_of(name, implicit = True):
        default = PathogenVersion(f"{name}@{default}")
    else:
        default = None

    return default, configured_default


def default_version_of(name: str, implicit: bool = True, versions: List[str] = None) -> Optional[str]:
    """
    Returns the default version string for the pathogen *name*.

    If the user config contains an explicit default, that value is returned.

    >>> default_version_of("from-config")
    'v1'

    Otherwise, if *implicit* is ``True`` (the default), then the filesystem is
    scanned for available versions of *name* and if there's only one setup, its
    version is returned.

    >>> default_version_of("with-implicit-default")
    '1.2.3'
    >>> default_version_of("with-implicit-default", implicit = False)
    >>>
    >>> default_version_of("with-no-implicit-default")
    >>>

    To avoid a filesystem scan for consistency (and performance in the limit)
    when it's been scanned already, a list of string *versions* may be passed.
    This is only used when no default is configured and *implicit* is ``True``.

    >>> default_version_of("with-cached-versions", versions = ["one"])
    'one'

    >>> default_version_of("with-cached-versions", versions = ["one", "two"])
    >>>

    >>> default_version_of("from-config", versions = ["one", "two"])
    'v1'

    If no default version can be determined, ``None`` is returned.

    >>> default_version_of("not-in-config")
    >>>
    >>> default_version_of("bogus")
    >>>
    """
    assert name
    default = config.get(f"pathogen {name}", "default_version")

    # The "implicit default" behaviour below makes the code (in
    # pathogen_defaults() above and in nextstrain/cli/setup.py) considerably
    # more complicated.  It's tempting to ditch the behaviour to ditch the
    # additional complexity.  But I think the implicit default also makes the
    # `nextstrain setup` and `nextstrain run` user interfaces more humane.  If
    # someone has only one version of a pathogen installed (as will be very
    # common), why should they have to remember to specify --set-default at
    # setup-time or the full version at run-time?  It would be annoying for the
    # computer to tell them, "hey, what version of 'measles' did you mean?"
    # when they only have one version of 'measles' installed!
    #
    # I dithered on this for a while, but I think it's worth taking on the
    # behind-the-scenes complexity in order to make the user interface more
    # compatible with human common sense.
    #   -trs, 10 Jan 2025
    #
    # See also our long discussion of this (mostly captured) on a PR review
    # thread: <https://github.com/nextstrain/cli/pull/407#discussion_r1990232730>
    #   -trs, 7 April 2025
    if not default and implicit:
        if versions is None:
            versions = versions_of(name)

        if len(versions) == 1:
            default = versions[0]

    return default or None


def versions_of(name: str) -> List[str]:
    """
    Scans the filesystem for setup versions of pathogen *name* and returns a
    list of version strings.

    Sorted as PEP-440-compliant versions (newest → oldest) then other textual
    versions (A → Z and 0 → 9, by parts).

    >>> versions_of("with-implicit-default")
    ['1.2.3']

    >>> versions_of("with-no-implicit-default")
    ['4.5.6', '1.2.3']

    >>> versions_of("bogus")
    []
    """
    return versions_within(PATHOGENS / name)


def versions_within(pathogen_dir: Path) -> List[str]:
    """
    Scans the filesystem for setup versions within *pathogen_dir* and returns a
    list of version strings.

    Sorted as PEP-440-compliant versions (newest → oldest) then other textual
    versions (A → Z and 0 → 9, by parts).
    """
    if not pathogen_dir.exists():
        return []

    return sorted_versions(
        PathogenVersion.decode_version_dir(d.name)
            for d in pathogen_dir.iterdir()
             if d.is_dir() )


def sorted_versions(vs: Iterable[str]) -> List[str]:
    """
    Sort newest → oldest for normal versions (e.g. 4.5.6, 1.2.3) and A → Z
    for non-compliant versions (e.g. branch names, commit ids, arbitrary
    strings, etc.), with the latter always after the former.

    The versions given should be strings.  The returned list of versions will
    be the same strings in sorted order.  Versions are parsed by
    :func:`parse_lax_version`.
    """
    versions = [*map(parse_version_lax, vs)]

    compliant     = sorted(v for v in versions if v.compliant)
    non_compliant = sorted(v for v in versions if not v.compliant)

    return [v.original for v in [*reversed(compliant), *non_compliant]]


def read_pathogen_registration(path: Path) -> Optional[Dict]:
    """
    Reads a ``nextstrain-pathogen.yaml`` file at *path* and returns a dict of
    its deserialized contents.

    Returns ``None`` if the path does not exist.

    Raises :exc:`RegistrationError` if there are issues with the registration.
    """
    # Read file
    try:
        with path.open("r", encoding = "utf-8") as f:
            registration = yaml.safe_load(f)

    except FileNotFoundError as err:
        debug(f"failed to read pathogen registration at {str(path)!r}:", err)
        return None

    # File exists and we read it.
    #
    # If it's an empty file (or contains only comments) as is common when the
    # file is used solely as a marker, then we'll get None.  Treat that as an
    # empty dict instead.
    if registration is None:
        registration = {}

    if not isinstance(registration, dict):
        raise RegistrationError(f"top-level not a dict (got a {type(registration).__name__})")

    # Locate schema for file, if any
    if not (schema_id := registration.get("$schema")):
        debug(f"skipping validation of pathogen registration {str(path)!r}: no $schema declared")
        return registration

    # Known schemas we can validate against
    schemas = {
        "https://nextstrain.org/schemas/pathogen/v0": "schema-pathogen-v0.json" }

    # Skip validation if schema is unknown
    if not (schema_path := schemas.get(schema_id)):
        debug(f"skipping validation of pathogen registration {str(path)!r}: unknown $schema: {schema_id!r}")
        return registration

    # Validate
    debug(f"validating pathogen registration against {schema_id!r} ({schema_path!r})")

    with resources.open_text(schema_path) as f:
        schema = json.load(f)

    assert schema.get("$id") == schema_id

    try:
        jsonschema.validate(registration, schema)
    except jsonschema.ValidationError as err:
        raise RegistrationError(f"Schema validation failed: {err.message}") from err

    return registration


class RegistrationError(InternalError):
    pass


# We query a nextstrain.org API instead of querying GitHub's API directly for a
# few reasons.
#
#  1. It gives us greater flexibility to move away from Git/GitHub-based
#     versioning and distribution in the future.
#  2. It gives us insight into usage.
#  3. It starts us down the road of a real Nextstrain pathogen registry.
#
#   -trs, 22 April 2025
def nextstrain_repo_latest_version(name: str) -> Optional[str]:
    """
    Queries a Nextstrain pathogen repo *name* to return the latest version,
    i.e. the name of the highest version tag, if any, otherwise the name of the
    default branch.
    """
    versions_url = URL(f"/pathogen-repos/{urlquote(name)}/versions", NEXTSTRAIN_DOT_ORG)

    with requests.Session() as http:
        response = http.get(str(versions_url), headers = {"Accept": "application/json"})

        if response.status_code == 404:
            return None
        else:
            response.raise_for_status()

        versions = sorted_versions(response.json().get("versions", []))

        return versions[0] if versions else None


def nextstrain_repo_zip_url(name: str, version: str) -> URL:
    """
    Queries a Nextstrain pathogen repo *name* to resolve *version* (i.e.
    currently any commit-ish) to a specific revision (i.e. commit id, SHA) if
    possible and returns a URL to a ZIP file of the repo contents at that
    revision.
    """
    # Quoting `version` _without_ the default `safe='/'` so that it gets
    # properly formatted as a single route parameter. Required for supporting
    # versions that are branch names with slashes. Note, I did not do the same
    # for `name` since GitHub repo names cannot contain slashes.
    #   -Jover, 18 July 2025
    version_url = URL(f"/pathogen-repos/{urlquote(name)}/versions/{urlquote(version, safe='')}", NEXTSTRAIN_DOT_ORG)

    with requests.Session() as http:
        resolved_version = http.get(str(version_url), headers = {"Accept": "application/json"})
        resolved_version.raise_for_status()

        if revision := resolved_version.json().get("revision"):
            return URL(urlquote(revision), version_url)
        else:
            return version_url

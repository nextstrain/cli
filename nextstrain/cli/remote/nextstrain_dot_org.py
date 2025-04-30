"""
.. versionadded:: 3.1.0

The ``nextstrain remote`` family of commands can
:doc:`list </commands/remote/list>`,
:doc:`download </commands/remote/download>`,
:doc:`upload </commands/remote/upload>`,
and :doc:`delete </commands/remote/delete>`
Nextstrain :term:`datasets <docs:dataset>` and :term:`narratives
<docs:narrative>` hosted on `nextstrain.org <https://nextstrain.org>`_.  This
functionality is primarily intended for users to manage the contents of their
:doc:`Nextstrain Groups <docs:learn/groups/index>`, but any public dataset or
narrative may be downloaded.


Remote paths
============

Nextstrain.org_ datasets and narratives are recognized by the same URLs used to
view them on the web, e.g. ``https://nextstrain.org/ncov/open/global``.

As a convenience, the scheme (``https://``) may be omitted, e.g.
``nextstrain.org/ncov/open/global``.

As a further convenience for Nextstrain Groups URLs, the domain
(``nextstrain.org``) may also be omitted, e.g.  ``groups/blab/sars-like-cov``
works as well as ``https://nextstrain.org/groups/blab/sars-like-cov``.


Authentication
==============

Read-only actions may be performed against public paths without authentication.
To manage a private Nextstrain Group or upload/delete a public path, first
login with nextstrain.org_ credentials using the :doc:`/commands/login`
command.


Environment variables
=====================

.. warning::
    For development only.  You don't need to set these during normal operation.

.. envvar:: NEXTSTRAIN_DOT_ORG

    Base URL to use instead of ``https://nextstrain.org`` when accessing
    remote resources, e.g.:

    .. code-block:: shell

        NEXTSTRAIN_DOT_ORG=http://localhost:5000 nextstrain remote ls nextstrain.org

    will interact with ``http://localhost:5000`` instead of nextstrain.org_.

.. envvar:: NEXTSTRAIN_DISABLE_NARRATIVE_IMAGE_EMBEDDING

    Set to any non-empty value to disable the automatic embedding of local
    images into narratives during upload.  The narrative's Markdown contents
    will be uploaded as-is, but any local images referenced by it will almost
    certainly be broken.
"""

import json
import os
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path, PurePosixPath
from shlex import quote as shquote
from tempfile import NamedTemporaryFile
from textwrap import indent, wrap
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple, Union
from urllib.parse import quote as urlquote
from .. import markdown
from .. import requests

# XXX TODO: These implement part of the RemoteModule protocol for us, which is
# sort of a weird way to organize things.  I think fine for now, esp. as
# there's only two remotes and only one of them (this one) supports authn, and
# so we have only one set of authn routines… but we may want to shuffle things
# around a bit internally in the future?
#   -trs, 21 Nov 2023
from ..authn import current_user, login, logout, renew  # noqa: F401 (see above)

from ..errors import UserError
from ..gzip import GzipCompressingReader
from ..net import is_loopback
from ..url import URL, Origin
from ..util import remove_prefix, glob_matcher, glob_match


# Default to embedding images, but allow it to be turned off as an escape
# hatch.
EMBED_IMAGES = not os.environ.get("NEXTSTRAIN_DISABLE_NARRATIVE_IMAGE_EMBEDDING")


# This subtype lets us use the type checker to catch places where code
# expects/assumes the semantics of normalize_path().
class NormalizedPath(PurePosixPath):
    ...


class Resource:
    """
    Base class for a remote Nextstrain resource described by its *path*.

    Concretely, either a :class:`Dataset` or :class:`Narrative` currently.
    """
    path: NormalizedPath
    subresources: List['SubResource']

    def __init__(self, path: str):
        self.path = normalize_path(path)


class SubResource(NamedTuple):
    """
    Info about a dataset or narrative subresource (i.e. file), representing
    both primary data and sidecars.

    media_type : str
        nextstrain.org RESTful API media type.

    file_extension : str
        File extension to use when saving this subresource to a file.

    primary : bool
        Flag indicating if this subresource is the resource's primary data.
    """
    media_type: str
    file_extension: str
    primary: bool = False

    def __str__(self) -> str:
        type, subtype = self.media_type.split("/", 1)
        subtype_sans_suffix, *_ = subtype.split("+", 1)
        subtype_tree = tuple(subtype_sans_suffix.split("."))

        resource = (
            "dataset"   if subtype_tree[0:3] == ("vnd", "nextstrain", "dataset")   else
            "narrative" if subtype_tree[0:3] == ("vnd", "nextstrain", "narrative") else
            self.media_type
        )

        sidecar = sidecar_suffix(self.media_type)

        return f"{resource} ({sidecar})" if sidecar else resource


class Dataset(Resource):
    """
    A remote Nextstrain dataset as described by its *path* and optional list of
    *sidecars*.
    """
    def __init__(self, path: str, sidecars: Optional[List[str]] = None):
        super().__init__(path)

        if sidecars is None:
            sidecars = ["root-sequence", "tip-frequencies", "measurements"]

        self.subresources = [
            SubResource("application/vnd.nextstrain.dataset.main+json", ".json", primary = True),

            *[SubResource(f"application/vnd.nextstrain.dataset.{type}+json", ".json")
                for type in sidecars],
        ]


class Narrative(Resource):
    """
    A remote Nextstrain narrative as described by its *path*.
    """
    subresources = [
        SubResource("text/vnd.nextstrain.narrative+markdown", ".md", primary = True),
    ]


def upload(url: URL, local_files: List[Path], dry_run: bool = False) -> Iterable[Tuple[Path, str]]:
    """
    Upload the *local_files* to the given nextstrain.org *url*.

    Doesn't actually upload anything if *dry_run* is truthy.
    """
    origin, path = url.origin, normalize_path(url.path)
    assert origin

    # XXX TODO: Consider changing the RemoteModule interface for upload() and
    # organizing files in the upload command's run() instead of here.  This
    # would make most sense as part of a larger UI rework of the `remote`
    # commands to focus on datasets/narratives rather than local/remote files.
    #
    #   -trs, 22 Sept 2021
    datasets, narratives, unknowns = organize_files(local_files)

    def file_list(files: Iterable):
        return indent("\n".join(map(str, files)), "    ")

    if unknowns:
        # XXX TODO: Handle group-logo.png and group-overview.md by making
        # appropriate API requests to the group endpoint (which doesn't yet
        # exist).
        #   -trs, 23 Sept 2021
        raise UserError(f"""
            Only datasets (v2) and narratives are currently supported for
            upload to nextstrain.org, but other files were given:

            {{files}}
            """, files = file_list(unknowns))

    if datasets and narratives_only(path):
        raise UserError(f"""
            The upload destination ({path}) is for narratives only,
            but dataset files were given for upload:

            {{files}}
            """, files = file_list(f for files in datasets.values() for f in files.values()))

    if narratives and not narratives_only(path) and prefixed(path):
        raise UserError(f"""
            The upload destination ({path}) includes a dataset path
            prefix, but narrative files were given for upload:

            {{files}}
            """, files = file_list(f for files in narratives.values() for f in files.values()))

    # If we're given a prefixed path (e.g. includes a narrative or dataset
    # name) and we only have a single dataset or narrative to upload, then we
    # use the given path as-is without using the local filename at all.  This
    # permits a simpler behaviour for a common starting use case of sharing a
    # single dataset or narrative.
    single = bool((len(datasets) + len(narratives)) == 1 and prefixed(path))

    with requests.Session() as http:
        http.auth = auth(origin)

        def put(endpoint, file, media_type):
            with GzipCompressingReader(file.open("rb")) as data:
                try:
                    response = http.put(
                        endpoint,
                        data = data,
                        headers = {
                            "Content-Type": media_type,
                            "Content-Encoding": "gzip" })

                except requests.exceptions.ConnectionError as err:
                    raw_err = err.args[0] if err.args else None

                    if isinstance(raw_err, BrokenPipeError):
                        raise UserError("""
                            The connection to the remote server was severed before the
                            upload finished.

                            Retrying may help if the problem happens to be transient (e.g. a
                            network error like a lost wifi signal), or there might be a bug
                            somewhere that needs to be fixed.

                            If retrying after a bit doesn't help, please open a new issue
                            at <https://github.com/nextstrain/cli/issues/new/choose> and
                            include the complete output above and the command you were
                            running.
                            """) from err
                    else:
                        raise

                raise_for_status(origin, response)

        # Upload datasets
        for dataset, files in datasets.items():
            for media_type, file in files.items():
                endpoint = destination = api_endpoint(origin, path if single else path / dataset)

                if media_type != "application/vnd.nextstrain.dataset.main+json":
                    destination += f" ({sidecar_suffix(media_type)})"

                yield file, destination

                if dry_run:
                    continue

                put(endpoint, file, media_type)

        # Upload narratives
        for narrative, files in narratives.items():
            markdown_type = "text/vnd.nextstrain.narrative+markdown"

            assert set(files) == {markdown_type}, files

            file = files[markdown_type]

            if not narratives_only(path):
                narrative = f"narratives/{narrative}"

            endpoint = destination = api_endpoint(origin, path if single else path / narrative)

            yield file, destination

            if dry_run:
                continue

            if EMBED_IMAGES:
                # Embed images into the narrative.
                #
                # Don't delete the temp file on close.  Allows us to manually close
                # the temp file so put() can reliably re-open it, per the docs¹:
                #
                #    Whether the name can be used to open the file a second time,
                #    while the named temporary file is still open, varies across
                #    platforms (it can be so used on Unix; it cannot on Windows).
                #
                # ¹ https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
                with NamedTemporaryFile("w", delete = False) as dst:
                    dst.write(
                        markdown.generate(
                            markdown.embed_images(
                                markdown.parse(file.read_text()),
                                file.resolve(strict = True).parent)))
                    dst.close()
                    put(endpoint, Path(dst.name), markdown_type)
            else:
                put(endpoint, file, markdown_type)


def download(url: URL, local_path: Path, recursively: bool = False, dry_run: bool = False) -> Iterable[Tuple[str, Path]]:
    """
    Download the datasets or narratives deployed at the given remote *url*,
    optionally *recursively*, saving them into the *local_dir*.

    Doesn't actually download anything if *dry_run* is truthy.
    """
    origin, path = url.origin, normalize_path(url.path)
    assert origin

    if str(path) == "/" and not recursively:
        raise UserError(f"""
            No path specified in URL ({url.geturl()}); nothing to download.

            Did you mean to use --recursively?
            """)

    with requests.Session() as http:
        http.auth = auth(origin)

        if recursively:
            resources = _ls(origin, path, recursively = recursively, http = http)
        else:
            # Avoid the query and just try to download the single resource.
            # This saves a request for single-dataset (or narrative) downloads,
            # but also allows downloading core datasets which aren't in the
            # manifest.  (At least until the manifest goes away.)
            #   -trs, 9 Nov 2022
            if narratives_only(path):
                resources = [Narrative(str(path))]
            else:
                resources = [Dataset(str(path))]

        if not resources:
            raise UserError(f"Path {path} does not seem to exist")

        for resource in resources:
            for subresource in resource.subresources:
                # Remote source
                endpoint = source = api_endpoint(origin, resource.path)

                if not subresource.primary:
                    source += f" ({sidecar_suffix(subresource.media_type)})"

                response = http.get(
                    endpoint,
                    headers = {"Accept": subresource.media_type},
                    stream = True)

                with response:
                    # Skip/ignore missing sidecars
                    if response.status_code == 404 and not subresource.primary:
                        continue

                    # Check for bad response
                    raise_for_status(origin, response)

                    if content_media_type(response) != subresource.media_type:
                        raise UserError(f"Path {path} does not seem to be a {subresource}.")

                    # Local destination
                    destination = _download_destination(resource, subresource, local_path)

                    yield source, destination

                    if dry_run:
                        continue

                    # Stream response data to local file
                    with destination.open("w") as local_file:
                        for chunk in response.iter_content(chunk_size = None, decode_unicode = True):
                            local_file.write(chunk)


def _download_destination(resource: Resource, subresource: SubResource, local_path: Path) -> Path:
    """
    These examples show all potential file names.

    >>> def names(r, d = Path.cwd()):
    ...    return [_download_destination(r, s, d).name for s in r.subresources]

    Dataset files.

    >>> names(Dataset("/ncov/open/global/6m")) # doctest: +NORMALIZE_WHITESPACE
    ['ncov_open_global_6m.json',
     'ncov_open_global_6m_root-sequence.json',
     'ncov_open_global_6m_tip-frequencies.json',
     'ncov_open_global_6m_measurements.json']

    Narrative files.

    >>> names(Narrative("/narratives/ncov/sit-rep/2020-01-23")) # doctest: +NORMALIZE_WHITESPACE
    ['ncov_sit-rep_2020-01-23.md']

    Namespace is omitted.

    >>> names(Dataset("/groups/blab/ncov-king-county/omicron")) # doctest: +NORMALIZE_WHITESPACE
    ['ncov-king-county_omicron.json',
     'ncov-king-county_omicron_root-sequence.json',
     'ncov-king-county_omicron_tip-frequencies.json',
     'ncov-king-county_omicron_measurements.json']

    When a non-directory local path is given.

    >>> names(Dataset("/mpox/clade-IIb"), Path("foo")) # doctest: +NORMALIZE_WHITESPACE
    ['foo.json',
     'foo_root-sequence.json',
     'foo_tip-frequencies.json',
     'foo_measurements.json']

    When a non-directory local path with extension is given.

    >>> names(Dataset("/mpox/clade-IIb"), Path("bar.json")) # doctest: +NORMALIZE_WHITESPACE
    ['bar.json',
     'bar_root-sequence.json',
     'bar_tip-frequencies.json',
     'bar_measurements.json']

    When a local path with non-extension dotted segment is given.

    >>> names(Dataset("/mpox/clade-IIb"), Path("mpox.clade-IIb")) # doctest: +NORMALIZE_WHITESPACE
    ['mpox.clade-IIb.json',
     'mpox.clade-IIb_root-sequence.json',
     'mpox.clade-IIb_tip-frequencies.json',
     'mpox.clade-IIb_measurements.json']

    When there are dots in the remote dataset name.

    >>> names(Dataset("/groups/niph/2022.04.29-ncov/omicron-BA-two")) # doctest: +NORMALIZE_WHITESPACE
    ['2022.04.29-ncov_omicron-BA-two.json',
     '2022.04.29-ncov_omicron-BA-two_root-sequence.json',
     '2022.04.29-ncov_omicron-BA-two_tip-frequencies.json',
     '2022.04.29-ncov_omicron-BA-two_measurements.json']

    When subresources don't share the same extension and may not have a sidecar
    suffix.  This is a hypothetical (though possible) use case for now, but
    demonstrates an edge case to consider in the code below.

    >>> r = Resource("/foo/bar")
    >>> r.subresources = [
    ...   SubResource("text/vnd.nextstrain.narrative+markdown", ".md", True),
    ...   SubResource("application/vnd.nextstrain.dataset.main+json", ".json"),
    ...   SubResource("application/vnd.nextstrain.dataset.root-sequence+json", ".json"),
    ... ]

    >>> names(r, Path("baz"))
    ['baz.md', 'baz.json', 'baz_root-sequence.json']

    >>> names(r, Path("baz.md"))
    ['baz.md', 'baz.json', 'baz_root-sequence.json']

    >>> names(r, Path("baz.bam"))
    ['baz.bam.md', 'baz.bam.json', 'baz.bam_root-sequence.json']
    """
    if local_path.is_dir():
        local_name = (
            str(resource.path.relative_to(namespace(resource.path)))
                .lstrip("/")
                .replace("/", "_"))

        destination = local_path / local_name
    else:
        # We assume a bit about subresource ordering here, so assert it.  Down
        # the road, it'd be better to enforce it structurally in Resource.
        #   -trs, 23 July 2024
        assert resource.subresources[0].primary, "first subresource is primary"
        assert all(not s.primary for s in resource.subresources[1:]), "subsequent subresources are not primary"

        # Strip the suffix provided by the user *iff* it matches our expected
        # *primary* extension; otherwise we assume they're intending to include
        # dots in their desired filename.
        if local_path.suffix == resource.subresources[0].file_extension:
            destination = local_path.with_suffix('')
        else:
            destination = local_path

    if not subresource.primary and (suffix := sidecar_suffix(subresource.media_type)):
        destination = destination.with_name(f"{destination.name}_{suffix}")

    destination = destination.with_name(destination.name + subresource.file_extension)

    return destination


def ls(url: URL) -> Iterable[str]:
    """
    List the datasets and narratives deployed at the given nextstrain.org *url*.
    """
    origin, path = url.origin, normalize_path(url.path)
    assert origin

    return [
        api_endpoint(origin, item.path)
            for item
             in _ls(origin, path, recursively = True)
    ]


def _ls(origin: Origin, path: NormalizedPath, recursively: bool = False, http: requests.Session = None):
    """
    List the :class:`Resource`(s) available on *origin* at *path*.

    If *recursively* is false (the default), then only an exact match of
    *path* is returned, if any.  If *recursively* is true, then all resources
    at or beneath *path* are returned.

    If *http* is not provided, a new :class:`requests.Session` will be created.
    obtain it.
    """
    if http is None:
        http = requests.Session()
        http.auth = auth(origin)

    response = http.get(
        api_endpoint(origin, "/charon/getAvailable"),
        params = {"prefix": str(path)},
        headers = {"Accept": "application/json"})

    raise_for_status(origin, response)

    available = response.json()

    def matches_path(x: Resource):
        if recursively:
            return x.path == path or glob_match(str(x.path), str(path / "**"))
        else:
            return x.path == path

    def to_dataset(api_item: dict) -> Dataset:
        # XXX TODO: The "sidecars" field in the /charon/getAvailable API
        # response doesn't actually exist yet and its use here is
        # prospective.
        #
        # I plan to extend the /charon/getAvailable API endpoint (or maybe
        # switch to a new endpoint) in the future to include the "sidecars"
        # field listing the available sidecars for each dataset, so that
        # this code only has to try to fetch what is reported to exist.
        # More than just reducing requests, the primary upshot is looser
        # coupling by avoiding the need to update the hardcoded list of
        # sidecars here and get people to upgrade their installed version
        # of this CLI if we add a new sidecar in the future.  Other API
        # clients would also likely benefit.
        #
        #   -trs, 18 August 2021
        #
        return Dataset(api_item["request"], api_item.get("sidecars"))

    def to_narrative(api_item: dict) -> Narrative:
        return Narrative(api_item["request"])

    return [
        *filter(matches_path, map(to_dataset, available["datasets"])),
        *filter(matches_path, map(to_narrative, available["narratives"])),
    ]


def delete(url: URL, recursively: bool = False, dry_run: bool = False) -> Iterable[str]:
    """
    Delete the datasets and narratives deployed at the given nextstrain.org
    *url*, optionally *recursively*.

    Doesn't actually delete anything if *dry_run* is truthy.
    """
    origin, path = url.origin, normalize_path(url.path)
    assert origin

    if str(path) == "/" and not recursively:
        raise UserError(f"""
            No path specified in URL ({url.geturl()}); nothing to download.

            Did you mean to use --recursively?
            """)

    with requests.Session() as http:
        http.auth = auth(origin)

        resources = _ls(origin, path, recursively = recursively, http = http)

        if not resources:
            raise UserError(f"Path {path} does not seem to exist")

        for resource in resources:
            endpoint = api_endpoint(origin, resource.path)

            yield endpoint

            if dry_run:
                continue

            response = http.delete(endpoint)

            raise_for_status(origin, response)

            assert response.status_code == 204


def normalize_path(path: str) -> NormalizedPath:
    """
    Ensure the URL *path* starts with a single ``/`` and ends without one, then
    wrap in a :class:`PurePosixPath` subclass (:class:`NormalizedPath`), for
    consistent comparison and handling purposes.

    >>> normalize_path("/groups/blab/")
    NormalizedPath('/groups/blab')
    >>> normalize_path("narratives/")
    NormalizedPath('/narratives')
    >>> normalize_path("")
    NormalizedPath('/')
    >>> normalize_path("/")
    NormalizedPath('/')
    """
    return NormalizedPath("/" + path.strip("/"))


def narratives_only(path: NormalizedPath) -> bool:
    """
    Test if *path* is specific to narratives.
    """
    return __narratives_only(str(path))


__narratives_only = glob_matcher([
    "/narratives{,/**}",
    "/staging/narratives{,/**}",
    "/groups/*/narratives{,/**}",
])


def prefixed(path: NormalizedPath) -> bool:
    """
    Test if *path* contains a prefix (i.e. path parts) beyond the top-level
    nextstrain.org namespaces ("source" in that codebase's parlance).

    >>> prefixed(normalize_path("groups/blab/abc"))
    True
    >>> prefixed(normalize_path("groups/blab/abc/def"))
    True
    >>> prefixed(normalize_path("groups/blab/narratives/abc"))
    True
    >>> prefixed(normalize_path("groups/blab/narratives/abc/def"))
    True
    >>> prefixed(normalize_path("groups/blab"))
    False
    >>> prefixed(normalize_path("groups/blab/narratives/"))
    False

    >>> prefixed(normalize_path("staging/wxyz"))
    True
    >>> prefixed(normalize_path("staging/tuv/wxyz"))
    True
    >>> prefixed(normalize_path("staging/narratives/tuv"))
    True
    >>> prefixed(normalize_path("staging/narratives/tuv/wxyz"))
    True
    >>> prefixed(normalize_path("staging"))
    False
    >>> prefixed(normalize_path("staging/narratives/"))
    False

    >>> prefixed(normalize_path("abc"))
    True
    >>> prefixed(normalize_path("abc/def"))
    True
    >>> prefixed(normalize_path("narratives/abc"))
    True
    >>> prefixed(normalize_path("narratives/abc/def"))
    True
    >>> prefixed(normalize_path("/"))
    False
    >>> prefixed(normalize_path("narratives/"))
    False
    """
    return str(path.relative_to(namespace(path))) != "."


def namespace(path: NormalizedPath) -> NormalizedPath:
    """
    Return the top-level nextstrain.org namespace ("source" in that codebase's
    parlance + optional "narratives/" part) for *path*.

    >>> namespace(normalize_path("groups/blab/abc"))
    NormalizedPath('/groups/blab')
    >>> namespace(normalize_path("groups/blab/abc/def"))
    NormalizedPath('/groups/blab')
    >>> namespace(normalize_path("groups/blab/narratives/abc"))
    NormalizedPath('/groups/blab/narratives')
    >>> namespace(normalize_path("groups/blab/narratives/abc/def"))
    NormalizedPath('/groups/blab/narratives')
    >>> namespace(normalize_path("groups/blab"))
    NormalizedPath('/groups/blab')
    >>> namespace(normalize_path("groups/blab/narratives/"))
    NormalizedPath('/groups/blab/narratives')

    >>> namespace(normalize_path("staging/wxyz"))
    NormalizedPath('/staging')
    >>> namespace(normalize_path("staging/tuv/wxyz"))
    NormalizedPath('/staging')
    >>> namespace(normalize_path("staging/narratives/tuv"))
    NormalizedPath('/staging/narratives')
    >>> namespace(normalize_path("staging/narratives/tuv/wxyz"))
    NormalizedPath('/staging/narratives')
    >>> namespace(normalize_path("staging"))
    NormalizedPath('/staging')
    >>> namespace(normalize_path("staging/narratives/"))
    NormalizedPath('/staging/narratives')

    >>> namespace(normalize_path("abc"))
    NormalizedPath('/')
    >>> namespace(normalize_path("abc/def"))
    NormalizedPath('/')
    >>> namespace(normalize_path("narratives/abc"))
    NormalizedPath('/narratives')
    >>> namespace(normalize_path("narratives/abc/def"))
    NormalizedPath('/narratives')
    >>> namespace(normalize_path("/"))
    NormalizedPath('/')
    >>> namespace(normalize_path("narratives/"))
    NormalizedPath('/narratives')
    """
    path_ = str(path)

    if glob_match(path_, "/groups/*/narratives{,/**}"):
        return normalize_path(f"/groups/{path.parts[2]}/narratives")

    elif glob_match(path_, "/groups/*{,/**}"):
        return normalize_path(f"/groups/{path.parts[2]}")

    elif glob_match(path_, "/staging/narratives{,/**}"):
        return normalize_path("/staging/narratives")

    elif glob_match(path_, "/staging{,/**}"):
        return normalize_path("/staging")

    elif glob_match(path_, "/narratives{,/**}"):
        return normalize_path("/narratives")

    else:
        return normalize_path("/")


def api_endpoint(origin: Origin, path: Union[str, PurePosixPath]) -> str:
    """
    Join the API *path* with the base API *origin* to produce a complete
    endpoint URL.

    >>> api_endpoint(URL("https://nextstrain.org").origin, "a/b/c")
    'https://nextstrain.org/a/b/c'

    >>> api_endpoint(URL("http://localhost:5000/").origin, "/a/b/c")
    'http://localhost:5000/a/b/c'

    >>> api_endpoint(URL("http://localhost:5000/x").origin, "//a/b/c")
    'http://localhost:5000/a/b/c'

    >>> api_endpoint(URL("http://localhost:5000/x/").origin, "a/b/c")
    'http://localhost:5000/a/b/c'
    """
    return origin + "/" + urlquote(str(path).lstrip("/"), safe = "/@")


class auth(requests.auth.AuthBase):
    """
    Authentication class for Requests which adds HTTP request headers to
    authenticate with the nextstrain.org (or alike) API as the CLI's currently
    logged in user, if any, for a given origin.
    """
    def __init__(self, origin: Origin):
        self.origin = origin
        self.user = current_user(origin)

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        url = URL(str(request.url))

        secure = url.scheme == "https" \
              or is_loopback(url.hostname)

        if self.user and url.origin == self.origin and self.user.origin == self.origin and secure:
            request.headers["Authorization"] = self.user.http_authorization

            # Used in error handling for more informative error messages
            request._user = self.user # pyright: ignore[reportAttributeAccessIssue]

        return request


def raise_for_status(origin: Origin, response: requests.Response) -> None:
    """
    Human-centered error handling for nextstrain.org API responses.

    Calls :meth:`requests.Response.raise_for_status` and handles statuses:

    - 400
    - 401
    - 403
    - 404
    - 5xx

    Unhandled errors are re-raised so callers can handle them.
    """
    try:
        response.raise_for_status()

    except requests.exceptions.HTTPError as err:
        assert type(err.response) is requests.Response
        status = err.response.status_code

        if status == 400:
            try:
                msg = json.loads(response.content)["error"]
            except (json.JSONDecodeError, KeyError):
                raise err from None
            else:
                raise UserError("""
                    The remote server rejected our request:

                    {msg}

                    This may indicate a problem that's fixable by you, or it
                    may be a bug somewhere that needs to be fixed by the
                    Nextstrain developers.

                    If you're unable to address the problem, please open a new
                    issue at <https://github.com/nextstrain/cli/issues/new/choose>
                    and include the complete output above and the command you
                    were running.
                    """, msg = indent("\n".join(wrap(msg)), "  ")) from err

        elif status in {401, 403}:
            try:
                user = response.request._user # pyright: ignore[reportAttributeAccessIssue]
            except AttributeError:
                user = None

            if user:
                challenge = authn_challenge(response) if status == 401 else None

                if challenge and challenge.get("error") == "invalid_token":
                    # XXX TODO: In the future we could/should handle renewal
                    # and retry automatically and ~transparently.
                    #
                    # Instead of throwing a UserError, this bit of code could
                    # throw a custom exception, InvalidTokenError or something,
                    # which would be caught by upper layers (caller of
                    # raise_for_status()?) and be the trigger for performing
                    # the renew and retry.
                    #
                    # Could potentially also use the "response" hook supported
                    # by Requests and/or a urllib3 Retry subclass
                    # implementation, but if the caller of raise_for_status()
                    # isn't involved then the retry needs to be generalized
                    # enough to handle things like re-seeking streams (which
                    # may not be possible without cooperation).
                    #   -trs, 10 May 2022
                    raise UserError(f"""
                        Login credentials appear to be out of date.

                        Please run

                            nextstrain login --renew {shquote(origin)}

                        and then retry your command.
                        """) from err
                else:
                    raise UserError(f"""
                        Permission denied.

                        Are you logged in as the correct user?

                        Current user: {user.username}

                        If your permissions were recently changed (e.g. new group
                        membership), it might help to run

                            nextstrain login --renew {shquote(origin)}

                        and then retry your command.
                        """) from err
            else:
                raise UserError(f"""
                    Permission denied.

                    Logging in with

                        nextstrain login {shquote(origin)}

                    might help?
                    """) from err

        elif status == 404:
            raise UserError("""
                Remote resource not found.

                Check for typos in the parameters you used?
                """) from err

        elif status in range(500, 600):
            raise UserError("""
                The remote server had a problem processing our request.

                Retrying may help if the problem happens to be transient, or
                there might be a bug somewhere that needs to be fixed.

                If retrying after a bit doesn't help, please open a new issue
                at <https://github.com/nextstrain/cli/issues/new/choose> and
                include the complete output above and the command you were
                running.
                """) from err

        else:
            raise


def authn_challenge(response: requests.Response) -> Optional[Dict[str, str]]:
    """
    Extract the Bearer authentication challenge parameters from the HTTP
    ``WWW-Authenticate`` header of *response*.

    >>> r = requests.Response()
    >>> r.headers["WWW-Authenticate"] = 'Bearer error="invalid_token", error_description="token is expired"'
    >>> authn_challenge(r)
    {'error': 'invalid_token', 'error_description': 'token is expired'}

    >>> r = requests.Response()
    >>> r.headers["WWW-Authenticate"] = 'Basic realm="nunya"'
    >>> authn_challenge(r) # None

    >>> r = requests.Response()
    >>> authn_challenge(r) # None

    A limitation is that this assumes only one challenge is provided, though
    multiple challenges are permitted by the RFCs.  The Bearer challenge must
    be first to be found:

    >>> r = requests.Response()
    >>> r.headers["WWW-Authenticate"] = 'Basic realm="nunya", Bearer error="invalid_token"'
    >>> authn_challenge(r) # None

    and challenges following an initial Bearer challenge will be parsed
    incorrectly as params:

    >>> r = requests.Response()
    >>> r.headers["WWW-Authenticate"] = 'Bearer error="invalid_token", Basic realm="nunya"'
    >>> authn_challenge(r)
    {'error': 'invalid_token', 'Basic realm': 'nunya'}
    """
    challenge = response.headers.get("WWW-Authenticate")

    if not challenge or not challenge.startswith("Bearer "):
        return None

    challenge_params = remove_prefix("Bearer ", challenge).lstrip(" ")

    return requests.utils.parse_dict_header(challenge_params)


def content_media_type(response: requests.Response) -> str:
    """
    Extract the media (MIME) type from the ``Content-Type`` header of
    *response*.

    Ignores any parameters that may be part of the header value, like
    ``charset``.

    If no ``Content-Type`` value exists, returns the fallback type
    ``application/octet-stream``.
    """
    # requests.Response provides no way to parse the media (MIME) type from the
    # Content-Type, but we can use EmailMessage from the standard library to do
    # so instead!
    msg = EmailMessage()

    if "Content-Type" in response.headers:
        msg["Content-Type"] = response.headers["Content-Type"]

    msg.set_default_type("application/octet-stream")

    return msg.get_content_type()


class OrganizedFiles(NamedTuple):
    datasets:   Dict[str, Dict[str, Path]]
    narratives: Dict[str, Dict[str, Path]]
    unknowns:   List[Path]


def organize_files(paths: Iterable[Path]) -> OrganizedFiles:
    """
    Organizes the given *paths* into datasets, narratives, and unknowns.

    Dataset sidecars are grouped together with their related primary datasets
    files.

    Returns a :class:`OrganizedFiles` tuple.
    """
    # v1 dataset suffixes + our three dataset sidecar suffixes.
    #
    # There are other conventional suffixes for node data files (see our data
    # formats doc¹), but we're not trying to handle node data files here.
    #
    # ¹ https://docs.nextstrain.org/en/latest/reference/data-formats.html
    dataset_suffixes = {"meta", "tree", "root-sequence", "tip-frequencies", "measurements"}

    datasets:   Dict[str, Dict[str, Path]] = defaultdict(dict)
    narratives: Dict[str, Dict[str, Path]] = defaultdict(dict)
    unknowns: List[Path] = []

    for path in paths:
        # XXX TODO: In the future, in addition or instead of using filename
        # conventions, we might want to identify files using partial content
        # inspection (e.g. does the file contain the expected top-level keys
        # for a given sidecar type?) or full schema validation (e.g. try to
        # validate all schemas and see which passes).
        #
        #   -trs, 19 August 2021
        #
        if path.suffix == ".json":
            if any(path.stem.endswith("_" + s) for s in dataset_suffixes):
                name, suffix = path.stem.rsplit("_", 1)
            else:
                name, suffix = path.stem, ""

            media_type = dataset_media_type(suffix)

            if media_type:
                datasets[name.replace("_", "/")][media_type] = path
            else:
                unknowns.append(path)

        elif path.suffix == ".md" and path.stem != "group-overview":
            narratives[path.stem.replace("_", "/")]["text/vnd.nextstrain.narrative+markdown"] = path

        else:
            unknowns.append(path)

    return OrganizedFiles(
        dict(sorted(datasets.items())),
        dict(sorted(narratives.items())),
        sorted(unknowns)
    )


def sidecar_suffix(media_type: str) -> str:
    suffixes = {
        "application/vnd.nextstrain.dataset.root-sequence+json": "root-sequence",
        "application/vnd.nextstrain.dataset.tip-frequencies+json": "tip-frequencies",
        "application/vnd.nextstrain.dataset.measurements+json": "measurements",
    }
    return suffixes.get(media_type, "")


def dataset_media_type(suffix: str) -> Optional[str]:
    media_types = {
        "": "application/vnd.nextstrain.dataset.main+json",
        "root-sequence": "application/vnd.nextstrain.dataset.root-sequence+json",
        "tip-frequencies": "application/vnd.nextstrain.dataset.tip-frequencies+json",
        "measurements": "application/vnd.nextstrain.dataset.measurements+json",
    }
    return media_types.get(suffix)

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
    For development only.  You don't need to set this during normal operation.

.. envvar:: NEXTSTRAIN_DOT_ORG

    Base URL to use instead of ``https://nextstrain.org`` when accessing
    remote resources, e.g.:

    .. code-block:: shell

        NEXTSTRAIN_DOT_ORG=http://localhost:5000 nextstrain remote ls nextstrain.org

    will interact with ``http://localhost:5000`` instead of nextstrain.org_.
"""

import os
import requests
import requests.auth
import urllib.parse
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path, PurePosixPath
from requests.utils import parse_dict_header
from textwrap import indent
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple, Union
from urllib.parse import urljoin, urlsplit, quote as urlquote
from ..authn import current_user
from ..errors import UserError
from ..gzip import GzipCompressingReader
from ..util import remove_prefix, glob_matcher, glob_match


NEXTSTRAIN_DOT_ORG = os.environ.get("NEXTSTRAIN_DOT_ORG") \
                  or "https://nextstrain.org"


# This subtype lets us use the type checker to catch places where code
# expects/assumes the semantics of normalize_path().
class NormalizedPath(PurePosixPath):
    ...


class Resource:
    """
    Base class for a remote Nextstrain resource, as described by a Charon API
    "getAvailable" response.

    Concretely, either a :class:`Dataset` or :class:`Narrative` currently.
    """
    path: NormalizedPath
    subresources: List['SubResource']

    def __init__(self, api_item: dict):
        self.path = normalize_path(api_item["request"])


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


class Dataset(Resource):
    """
    A remote Nextstrain dataset, as described by a Charon API response,
    extended for the nextstrain.org RESTful API.
    """
    def __init__(self, api_item):
        super().__init__(api_item)

        default_sidecars = ["root-sequence", "tip-frequencies", "measurements"]

        self.subresources = [
            SubResource("application/vnd.nextstrain.dataset.main+json", ".json", primary = True),

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
            *[SubResource(f"application/vnd.nextstrain.dataset.{type}+json", ".json")
                for type in api_item.get("sidecars", default_sidecars)],
        ]


class Narrative(Resource):
    """
    A remote Nextstrain narrative, as described by a Charon API response,
    extended for the nextstrain.org RESTful API.
    """
    subresources = [
        SubResource("text/vnd.nextstrain.narrative+markdown", ".md", primary = True),
    ]


def upload(url: urllib.parse.ParseResult, local_files: List[Path], dry_run: bool = False) -> Iterable[Tuple[Path, str]]:
    """
    Upload the *local_files* to the given nextstrain.org *url*.

    Doesn't actually upload anything if *dry_run* is truthy.
    """
    path = remote_path(url)

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
        raise UserError("""
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
        http.auth = auth()

        def put(endpoint, file, media_type):
            with GzipCompressingReader(file.open("rb")) as data:
                try:
                    response = http.put(
                        endpoint,
                        data = data, # type: ignore
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

                raise_for_status(response)

        # Upload datasets
        for dataset, files in datasets.items():
            for media_type, file in files.items():
                endpoint = destination = api_endpoint(path if single else path / dataset)

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

            endpoint = destination = api_endpoint(path if single else path / narrative)

            yield file, destination

            if dry_run:
                continue

            put(endpoint, file, markdown_type)


def download(url: urllib.parse.ParseResult, local_path: Path, recursively: bool = False, dry_run: bool = False) -> Iterable[Tuple[str, Path]]:
    """
    Download the datasets or narratives deployed at the given remote *url*,
    optionally *recursively*, saving them into the *local_dir*.

    Doesn't actually download anything if *dry_run* is truthy.
    """
    path = remote_path(url)

    if str(path) == "/" and not recursively:
        raise UserError(f"""
            No path specified in URL ({url.geturl()}); nothing to download.

            Did you mean to use --recursively?
            """)

    with requests.Session() as http:
        http.auth = auth()

        resources = _ls(path, recursively = recursively, http = http)

        if not resources:
            raise UserError(f"Path {path} does not seem to exist")

        for resource in resources:
            for subresource in resource.subresources:
                # Remote source
                endpoint = source = api_endpoint(resource.path)

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
                    raise_for_status(response)
                    assert content_media_type(response) == subresource.media_type

                    # Local destination
                    if local_path.is_dir():
                        local_name = (
                            str(resource.path.relative_to(namespace(resource.path)))
                                .lstrip("/")
                                .replace("/", "_"))

                        destination = local_path / local_name
                    else:
                        destination = local_path

                    if not subresource.primary:
                        destination = destination.with_name(f"{destination.with_suffix('').name}_{sidecar_suffix(subresource.media_type)}")

                    destination = destination.with_suffix(subresource.file_extension)

                    yield source, destination

                    if dry_run:
                        continue

                    # Stream response data to local file
                    with destination.open("w") as local_file:
                        for chunk in response.iter_content(chunk_size = None, decode_unicode = True):
                            local_file.write(chunk)


def ls(url: urllib.parse.ParseResult) -> Iterable[str]:
    """
    List the datasets and narratives deployed at the given nextstrain.org *url*.
    """
    path = remote_path(url)

    return [
        api_endpoint(item.path)
            for item
             in _ls(path, recursively = True)
    ]


def _ls(path: NormalizedPath, recursively: bool = False, http: requests.Session = None):
    """
    List the :class:`Resource`(s) available at *path*.

    If *recursively* is false (the default), then only an exact match of
    *path* is returned, if any.  If *recursively* is true, then all resources
    at or beneath *path* are returned.

    If *http* is not provided, a new :class:`requests.Session` will be created.
    obtain it.
    """
    if http is None:
        http = requests.Session()
        http.auth = auth()

    response = http.get(
        api_endpoint("charon/getAvailable"),
        params = {"prefix": str(path)},
        headers = {"Accept": "application/json"})

    raise_for_status(response)

    available = response.json()

    def matches_path(x: Resource):
        if recursively:
            return x.path == path or glob_match(str(x.path), str(path / "**"))
        else:
            return x.path == path

    return [
        *filter(matches_path, map(Dataset, available["datasets"])),
        *filter(matches_path, map(Narrative, available["narratives"])),
    ]


def delete(url: urllib.parse.ParseResult, recursively: bool = False, dry_run: bool = False) -> Iterable[str]:
    """
    Delete the datasets and narratives deployed at the given nextstrain.org
    *url*, optionally *recursively*.

    Doesn't actually delete anything if *dry_run* is truthy.
    """
    path = remote_path(url)

    if str(path) == "/" and not recursively:
        raise UserError(f"""
            No path specified in URL ({url.geturl()}); nothing to download.

            Did you mean to use --recursively?
            """)

    with requests.Session() as http:
        http.auth = auth()

        resources = _ls(path, recursively = recursively, http = http)

        if not resources:
            raise UserError(f"Path {path} does not seem to exist")

        for resource in resources:
            yield "nextstrain.org" + str(resource.path)

            if dry_run:
                continue

            response = http.delete(api_endpoint(resource.path))

            raise_for_status(response)

            assert response.status_code == 204


def remote_path(url: urllib.parse.ParseResult) -> NormalizedPath:
    """
    Extract the remote path, or "prefix" in nextstrain.org parlance, from a
    nextstrain.org *url*.
    """
    assert url.netloc.lower() == "nextstrain.org"
    return normalize_path(url.path)


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


def api_endpoint(path: Union[str, PurePosixPath]) -> str:
    """
    Join the API *path* with the base API URL to produce a complete endpoint URL.
    """
    return urljoin(NEXTSTRAIN_DOT_ORG, urlquote(str(path).lstrip("/")))


class auth(requests.auth.AuthBase):
    """
    Authentication class for Requests which adds HTTP request headers to
    authenticate with the nextstrain.org API as the CLI's currently logged in
    user, if any.
    """
    def __init__(self):
        self.user = current_user()

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        if self.user and origin(request.url) == origin(NEXTSTRAIN_DOT_ORG):
            request.headers["Authorization"] = self.user.http_authorization
        return request


def origin(url: Optional[str]) -> Tuple[str, str]:
    """
    Parse *url* and into its origin tuple (scheme, netloc).

    >>> origin("https://nextstrain.org/a/b/c")
    ('https', 'nextstrain.org')

    >>> origin("http://localhost:5000/x/y/z")
    ('http', 'localhost:5000')
    """
    u = urlsplit(url or "")
    return u.scheme, u.netloc


def raise_for_status(response: requests.Response) -> None:
    """
    Human-centered error handling for nextstrain.org API responses.

    Calls :meth:`requests.Response.raise_for_status` and handles statuses:

    - 401
    - 403
    - 404
    - 5xx

    Unhandled errors are re-raised so callers can handle them.
    """
    try:
        response.raise_for_status()

    except requests.exceptions.HTTPError as err:
        status = err.response.status_code

        if status in {401, 403}:
            user = current_user()

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
                    raise UserError("""
                        Login credentials appear to be out of date.

                        Please run `nextstrain login --renew` and then retry your command.
                        """) from err
                else:
                    raise UserError(f"""
                        Permission denied.

                        Are you logged in as the correct user?  Current user: {user.username}.

                        If your permissions were recently changed (e.g. new group
                        membership), it might help to run `nextstrain login --renew`
                        and then retry your command.
                        """) from err
            else:
                raise UserError("""
                    Permission denied.

                    Logging in with `nextstrain login` might help?
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

    return parse_dict_header(challenge_params)


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

    msg["Content-Type"] = response.headers.get("Content-Type")
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

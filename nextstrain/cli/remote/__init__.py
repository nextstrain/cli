"""
Remote destinations and sources for Nextstrain datasets and narratives.
"""

import re
from typing import Tuple
from ..errors import UserError
from ..net import is_loopback
from ..rst import doc_url
from ..types import RemoteModule
from ..url import URL, NEXTSTRAIN_DOT_ORG
from . import s3, nextstrain_dot_org


def parse_remote_path(path: str) -> Tuple[RemoteModule, URL]:
    """
    Nextstrain.org is accessed via HTTPS URLs:

    >>> parse_remote_path("https://nextstrain.org/abc/def") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='https', netloc='nextstrain.org', path='/abc/def', query='', fragment=''))

    The scheme is optional:

    >>> parse_remote_path("nextstrain.org/abc/def") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='https', netloc='nextstrain.org', path='/abc/def', query='', fragment=''))

    >>> parse_remote_path("localhost:5000") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='http', netloc='localhost:5000', path='', query='', fragment=''))

    And as a special-case for Nextstrain Groups, the domain/host is optional
    too:

    >>> parse_remote_path("groups/xyz/abc") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='https', netloc='nextstrain.org', path='/groups/xyz/abc', query='', fragment=''))

    Other HTTP(S) URLs are also permitted for testing/development/alternative
    instances:

    >>> parse_remote_path("http://localhost:5000/xyz") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='http', netloc='localhost:5000', path='/xyz', query='', fragment=''))

    When no scheme is specified, HTTPS is assumed:

    >>> parse_remote_path("example.com/xyz") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='https', netloc='example.com', path='/xyz', query='', fragment=''))

    with the exception of ``localhost`` where HTTP is assumed:

    >>> parse_remote_path("localhost:5000/xyz") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='http', netloc='localhost:5000', path='/xyz', query='', fragment=''))

    HTTP is not permitted except for loopback hosts:

    >>> parse_remote_path("http://example.com/abc/def")
    Traceback (most recent call last):
        ...
    cli.errors.UserError: Error: Unsupported remote specified: 'http://example.com/abc/def'
    <BLANKLINE>
    Insecure http:// protocol is allowed only for localhost and
    other loopback addresses.

    But note that we'll quietly switch to HTTPS for nextstrain.org even if
    given as HTTP:

    >>> parse_remote_path("http://nextstrain.org/abc/def") # doctest: +ELLIPSIS
    (<module 'cli.remote.nextstrain_dot_org' from ...>, URL(scheme='https', netloc='nextstrain.org', path='/abc/def', query='', fragment=''))

    S3 URLs are also supported:

    >>> parse_remote_path("s3://bucket/abc/xyz") # doctest: +ELLIPSIS
    (<module 'cli.remote.s3' from ...>, URL(scheme='s3', netloc='bucket', path='/abc/xyz', query='', fragment=''))

    Other schemes are not:

    >>> parse_remote_path("ftp://example.com/foo/bar") # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    cli.errors.UserError: Error: Unsupported remote specified: 'ftp://example.com/foo/bar'
    <BLANKLINE>
    Supported remotes are:
    <BLANKLINE>
      - nextstrain.org/…
      - s3://…
    ...
    """
    url = URL(path)

    # Rescue <example.com:5000/abc/xyz> by re-parsing with an explicitly empty
    # scheme.  It initially parses as ('example.com', '', '5000/abc/xyz')
    # instead of ('', 'example.com:5000', '/abc/xyz').
    if url.scheme and not url.netloc and re.search("^[0-9]+(/|$)", url.path):
        url = URL("//" + path)

    if not url.scheme or url.scheme in {"https", "http"}:
        if not url.scheme:
            if url.path.startswith("groups/"):
                # Special-case groups/… as a shortcut
                url = URL("https://nextstrain.org/" + path)
            else:
                # Re-parse with an empty scheme to split .netloc from .path if
                # necessary, e.g. with <example.com/foo/bar> but not
                # <example.com:123/foo/bar>.
                url = URL("//" + path)

                # Now set explicit scheme
                if url.hostname == "localhost":
                    url = url._replace(scheme = "http")
                else:
                    url = url._replace(scheme = "https")

        # NEXTSTRAIN_DOT_ORG overrides nextstrain.org, but doesn't mask that
        # it's done so: the manipulated value will be visible in command
        # output.
        #
        # Note that the default value of NEXTSTRAIN_DOT_ORG means that a
        # user-specified path of http://nextstrain.org/… will be quietly
        # treated as https://.
        if url.netloc.lower() == "nextstrain.org":
            url = url._replace(scheme = NEXTSTRAIN_DOT_ORG.scheme, netloc = NEXTSTRAIN_DOT_ORG.netloc)

        if url.scheme == "http" and not is_loopback(url.hostname):
            raise UserError(f"""
                Unsupported remote specified: {path!r}

                Insecure http:// protocol is allowed only for localhost and
                other loopback addresses.
                """)

        return nextstrain_dot_org, url

    elif url.scheme == "s3":
        return s3, url

    else:
        # XXX TODO: This implies s3:// is supported for our authn commands,
        # login/whoami/etc., but it's not.  We catch it elsewhere, but this
        # means we say one thing here but then say "actually no" when they
        # try.  In general this function is geared towards the `nextstrain
        # remote` commands not the authn commands.  We should improve that,
        # but it's a bit of shuffling/refactoring I can't do right now.
        #   -trs, 15 Nov 2023
        raise UserError(f"""
            Unsupported remote specified: {path!r}

            Supported remotes are:

              - nextstrain.org/…
              - s3://…

            Alternate nextstrain.org-like servers (such as internal Nextstrain
            Groups Server instances) may be accessed via their URL, e.g.:

              - nextstrain.example.com/groups/…
              - https://nextstrain.example.com/groups/…
              - http://localhost:5000/…

            For more information on remote URLs, see `nextstrain remote --help`
            or <{doc_url("/commands/remote/index")}>.
            """)

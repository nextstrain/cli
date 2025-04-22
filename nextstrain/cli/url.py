"""
URL handling.

Extended forms of :mod:`urllib.parse` with an API that fits a little better.
"""
import os
from typing import List, Mapping, NewType, Optional, Union
from urllib.parse import urlsplit, SplitResult, parse_qs as parse_query, urlencode as construct_query, urljoin


Origin = NewType("Origin", str)


class URL(SplitResult):
    """
    A parsed URL.

    Combines the parsing functionality of :func:`urllib.parse.urlsplit` with
    its resulting data tuple of :cls:`urllib.parse.SplitResult`.

    May be constructed only from a single *url* string.

    >>> u = URL("https://example.com:123/abc/def?x=y#z")
    >>> u
    URL(scheme='https', netloc='example.com:123', path='/abc/def', query='x=y', fragment='z')

    >>> u.hostname
    'example.com'

    >>> u.origin
    'https://example.com:123'

    Standard named tuple methods are available.

    >>> u = u._replace(netloc="example.org")
    >>> u
    URL(scheme='https', netloc='example.org', path='/abc/def', query='x=y', fragment='z')

    >>> u.origin
    'https://example.org'

    An optional *base* URL string or :cls:`URL` is accepted and combined with
    *url* using :func:`urllib.parse.urljoin` before parsing.

    >>> URL("def?x=y#z", "https://example.com:123/abc/")
    URL(scheme='https', netloc='example.com:123', path='/abc/def', query='x=y', fragment='z')

    >>> URL("https://example.com/abc/def?x=y#z", "https://example.com:123/xyz?n=42#abc")
    URL(scheme='https', netloc='example.com', path='/abc/def', query='x=y', fragment='z')
    """
    __slots__ = ()

    def __new__(cls, url: str, base: Union[str, 'URL'] = None) -> 'URL':
        return super().__new__(cls, *urlsplit(urljoin(str(base), url) if base else url))

    # This is for the type checkers, which otherwise consider URL.__init__ to
    # have a signature based on SplitResult.__new__ instead of our own __new__.
    # It's not clear to me *why* they do that, but this hint helps sort it out.
    #   -trs, 16 Nov 2023
    def __init__(self, url: str, base: Union[str, 'URL'] = None) -> None: ...

    def __str__(self) -> str:
        return self.geturl()

    @property
    def origin(self) -> Optional[Origin]:
        """
        The URL's origin, in the `web sense
        <https://developer.mozilla.org/en-US/docs/Glossary/Origin>`__.

        >>> u = URL("https://example.com:123/abc/def?x=y#z")
        >>> u
        URL(scheme='https', netloc='example.com:123', path='/abc/def', query='x=y', fragment='z')
        >>> u.origin
        'https://example.com:123'

        Origin is ``None`` if unless both :meth:`.scheme` and :meth:`.netloc`
        are present.

        >>> u = URL("/a/b/c")
        >>> u
        URL(scheme='', netloc='', path='/a/b/c', query='', fragment='')
        >>> u.origin is None
        True

        >>> u = URL("//example.com/a/b/c")
        >>> u
        URL(scheme='', netloc='example.com', path='/a/b/c', query='', fragment='')
        >>> u.origin is None
        True
        """
        if self.scheme and self.netloc:
            return Origin(self.scheme + "://" + self.netloc)
        else:
            return None

    @property
    def query_fields(self) -> Mapping[str, List[str]]:
        """
        The URL's :attr:`.query` string parsed into a mapping of name-value fields.

        Values are always lists, even if the field name is not repeated in the
        query string.

        >>> URL("?x=y&a=1&b=2&x=z").query_fields
        {'x': ['y', 'z'], 'a': ['1'], 'b': ['2']}

        Fields without values are treated as having an empty string value.

        >>> URL("?x=&y&z=1").query_fields
        {'x': [''], 'y': [''], 'z': ['1']}
        """
        return parse_query(self.query, keep_blank_values = True)


def query(fields: Mapping[str, Union[str, List[str]]]) -> str:
    """
    Convert query *fields* to a query string.

    >>> query({'x': ['y', 'z'], 'a': ['1'], 'b': ['2']})
    'x=y&x=z&a=1&b=2'

    >>> query({'x': ['y', 'z'], 'a': '123', 'b': '456'})
    'x=y&x=z&a=123&b=456'

    >>> query({'x': [''], 'y': '', 'z': '123'})
    'x=&y=&z=123'
    """
    return construct_query(fields, doseq = True, encoding = "utf-8")


NEXTSTRAIN_DOT_ORG = URL(
       os.environ.get("NEXTSTRAIN_DOT_ORG")
    or "https://nextstrain.org")

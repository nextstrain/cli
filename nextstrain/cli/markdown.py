"""
Markdown parsing and rewriting for embedding narrative images.

Contains a Parsing Expression Grammar (PEG) for parsing Markdown with
:py:mod:`pyparsing`.  The grammar expects a complete Markdown document, but
only parses the minimal number of Markdown constructs required for our needs
(namely, embedding narrative images).

The two most useful documentation pages for pyparsing are its
`general usage overview <https://pyparsing-docs.readthedocs.io/en/latest/HowToUsePyparsing.html>`__ and
`API reference <https://pyparsing-docs.readthedocs.io/en/latest/pyparsing.html>`__,
which contains more details for each class than the usage doc.

Existing Markdown parsers, though many, all fell short of our use case of
transforming some input Markdown to some other output Markdown.  They all focus
on converting Markdown to HTML.  As such, they throw away important original
source text during the parse, thus making it impossible to reconstruct with any
fidelity and very difficult/tedious to produce more Markdown (i.e. you have to
cover all constructs).  I evaluted
`Markdown <https://pypi.org/project/Markdown/>`__,
`commonmark <https://pypi.org/project/commonmark/>`,
`markdown-it-py <https://pypi.org/project/markdown-it-py/>`__
(what I thought going into this would be our preferred choice!),
`mistletoe <https://pypi.org/project/mistletoe/>`__,
and `mistune <https://pypi.org/project/mistune/>`__.
"""
from base64 import b64encode
from copy import copy
import mimetypes
import re
from dataclasses import dataclass
from enum import Enum
from operator import attrgetter
from pathlib import Path
from pyparsing import (
    Group,
    LineEnd,
    LineStart,
    nested_expr,
    ParserElement,
    QuotedString,
    SkipTo,
    StringEnd,
    White,
    ZeroOrMore,
)
from typing import ClassVar, Generator, Iterable, Optional, Union
from urllib.parse import urlsplit, quote as urlquote


# The AST-like nodes we generate here for parsed elements follow the mdast
# spec¹.  We have to have _some_ data model, so might as well use an existing
# one to a) avoid coming up with our own and b) help us to think about cases we
# might not consider.  Note that we don't actually construct an AST, but
# produce a simpler flat list of nodes.
#   -trs, 17 Nov 2022
#
# ¹ https://github.com/syntax-tree/mdast
@dataclass
class Node:
    type: ClassVar[str] = "node"

@dataclass
class ResourceMixin:
    url: str
    title: Optional[str] = None

@dataclass
class AlternativeMixin:
    alt: Optional[str]

@dataclass
class AssociationMixin:
    identifier: str
    label: Optional[str]

class ReferenceType(Enum):
    full = "full"
    collapsed = "collapsed"
    shortcut = "shortcut"

@dataclass
class ReferenceMixin(AssociationMixin):
    referenceType: ReferenceType

@dataclass
class ImageNode(Node, ResourceMixin, AlternativeMixin):
    type: ClassVar[str] = "image"

@dataclass
class ImageReferenceNode(Node, AlternativeMixin, ReferenceMixin):
    type: ClassVar[str] = "imageReference"

@dataclass
class DefinitionNode(Node, ResourceMixin, AssociationMixin):
    type: ClassVar[str] = "definition"

@dataclass
class CodeNode(Node):
    type: ClassVar[str] = "code"
    lang: Optional[str]
    meta: Optional[str]
    value: str # from mdast's Literal


# Don't skip newlines when skipping whitespace.
#
# XXX TODO: This will affect *global* usage of pyparsing within this process,
# which may have unintended effects.  Currently we don't seem to have any
# dependents which also use pyparsing (without vendoring), so this seems ok.
# It's not clear to me at the moment how to properly configure each of our
# individual elements instead, but we should probably figure that out at some
# point.
#   -trs, 18 Nov 2022
ParserElement.set_default_whitespace_chars(" \t")


# Nested brackets are acceptable within outer brackets, e.g. of image alt text,
# as long as they're balanced.
BalancedBrackets = nested_expr(*"[]")


# ![alt](url "title")
# ![alt](url)
Title = QuotedString('"', esc_char = "\\", unquote_results = False, convert_whitespace_escapes = False)("title")
ImageWithTitle    = Group("![" + SkipTo("](", ignore = BalancedBrackets)("alt") + "](" + SkipTo(White())("url") + Title + ")")
ImageWithoutTitle = Group("![" + SkipTo("](", ignore = BalancedBrackets)("alt") + "](" + SkipTo(")")("url")             + ")")
Image = ((ImageWithTitle | ImageWithoutTitle)
    .set_name("Image"))

# https://github.com/syntax-tree/mdast#image
Image.set_parse_action(lambda tokens: ImageNode(
    alt = tokens[0]["alt"],
    url = tokens[0]["url"],
    title = tokens[0].get("title"),
))


# ![alt][label]  a "full" reference
# ![alt][]       a "collapsed" reference
# ![alt]         a "shortcut" reference
ImageReferenceExplicit = Group("![" + SkipTo("][", ignore = BalancedBrackets)("alt") + "][" + SkipTo("]")("label") + "]")
ImageReferenceImplicit = Group("![" + SkipTo("]",  ignore = BalancedBrackets)("alt") + "]")
ImageReference = ((ImageReferenceExplicit | ImageReferenceImplicit)
    .set_name("ImageReference"))

# https://github.com/syntax-tree/mdast#imagereference
ImageReference.set_parse_action(lambda tokens: ImageReferenceNode(
    alt = tokens[0]["alt"],
    label = tokens[0].get("label"),
    identifier = normalize_label(tokens[0].get("label") or tokens[0].get("alt")),
    referenceType = reference_type(tokens[0].get("label")),
))


# [label]: url
Definition = (Group(LineStart() + "[" + SkipTo("]:")("label") + "]:" + SkipTo(LineEnd())("url"))
    .set_name("Definition"))

# https://github.com/syntax-tree/mdast#definition
Definition.set_parse_action(lambda tokens: DefinitionNode(
    label = tokens[0]["label"],
    identifier = normalize_label(tokens[0]["label"]),
    url = tokens[0]["url"],
))


# ```auspiceMainDisplayMarkdown
# ... (unparsed)
# ```
AuspiceMainDisplayMarkdownStart = LineStart() + "```auspiceMainDisplayMarkdown" + LineEnd()
AuspiceMainDisplayMarkdownEnd = LineStart() + "```" + LineEnd()
AuspiceMainDisplayMarkdown = (Group(AuspiceMainDisplayMarkdownStart + ... + AuspiceMainDisplayMarkdownEnd)
    .set_name("AuspiceMainDisplayMarkdown"))

# Specific case of the more general https://github.com/syntax-tree/mdast#code;
# we don't parse all code blocks.
AuspiceMainDisplayMarkdown.set_parse_action(lambda tokens: CodeNode(
    lang  = "auspiceMainDisplayMarkdown",
    meta  = None,
    value = "".join(tokens[0].get("_skipped", [])),
))


# Parse just what we need to and pass thru the rest.
ParsedMarkdown = Image | ImageReference | Definition | AuspiceMainDisplayMarkdown
UnparsedMarkdown = SkipTo(ParsedMarkdown)
Markdown = ZeroOrMore(ParsedMarkdown | UnparsedMarkdown) + SkipTo(StringEnd())


NodeListNode = Union[Node, str]
NodeList = Iterable[NodeListNode]


def parse(markdown: str) -> NodeList:
    """
    Parse a *markdown* string into a flat list of nodes consisting of
    :py:cls:`Node` subclasses for parsed constructs and plain strings for raw,
    unparsed content.
    """
    return list(Markdown.parse_string(markdown, parse_all = True))


def generate(nodes: NodeList) -> str:
    """
    Generate Markdown from the given *nodes* list, such as that returned by
    :func:`parse`.
    """
    return "".join(_generate(nodes))


def _generate(nodes: NodeList):
    for node in nodes:
        if isinstance(node, str):
            yield node

        elif isinstance(node, ImageNode):
            alt, url, title = attrgetter("alt", "url", "title")(node)

            if title is not None:
                yield f"![{alt}]({url} {title})"
            else:
                yield f"![{alt}]({url})"

        elif isinstance(node, ImageReferenceNode):
            alt, label, identifier, referenceType = attrgetter("alt", "label", "identifier", "referenceType")(node)

            if referenceType is ReferenceType.full:
                yield f"![{alt}][{label or identifier}]"
            elif referenceType is ReferenceType.collapsed:
                yield f"![{alt}][]"
            elif referenceType is ReferenceType.shortcut:
                yield f"![{alt}]"

            else:
                raise AssertionError(f"unknown image reference type {referenceType!r} in node: {node!r}")

        elif isinstance(node, DefinitionNode):
            label, identifier, url = attrgetter("label", "identifier", "url")(node)
            yield f"[{label or identifier}]: {url}"

        elif isinstance(node, CodeNode) and node.lang == "auspiceMainDisplayMarkdown":
            yield f"```auspiceMainDisplayMarkdown\n"
            yield node.value
            yield f"```\n"

        else:
            raise AssertionError(f"unknown Markdown node: {node!r}")


def embed_images(nodes: NodeList, base_path: Path) -> NodeList:
    """
    Return a modified *nodes* list with local images (potentially relative to
    *base_path*) converted to embedded ``data:`` URLs.

    In the case where *nodes* was parsed from a local Markdown file,
    *base_path* should be the containing directory of that file.

    Neither *nodes* itself nor its contained :cls:`Node` instances are modified
    in place.  Instead, new :cls:`Node` instances are constructed as necessary
    and unchanged nodes are passed thru unmodified to avoid potentially
    expensive copies.
    """
    # Collect definitions so we can look them up when we encounter a reference.
    # If there are duplicate ids, the first one (in source order) wins.
    definitions = {
        n.identifier: n
            for n in reversed(nodes)
             if isinstance(n, DefinitionNode) }

    # We'll modify "definitions" in the first pass as we go, so keep a copy of
    # the originals around for diffing in the second pass.
    original_definitions = copy(definitions)

    # First pass to create new definitions for the image data: URLs.
    def first_pass(nodes: NodeList) -> Generator[NodeListNode, None, None]:
        for node in nodes:
            if isinstance(node, ImageNode):
                data_url = as_data_url(node.url, base_path)

                if data_url:
                    # Image references can't have a title, so if we have a
                    # title we have to inline the long data: URL.
                    if node.title is not None:
                        yield ImageNode(
                            alt = node.alt,
                            url = data_url,
                            title = node.title)
                    else:
                        # Otherwise, we prefer to add a new definition and convert
                        # this image to an image reference so we can sequester the
                        # long data: URL definition to the bottom of the document.
                        definition = DefinitionNode(
                            label = node.url,
                            identifier = normalize_label(node.url),
                            url = data_url)
                        definitions[definition.identifier] = definition

                        yield ImageReferenceNode(
                            alt = node.alt,
                            label = definition.label,
                            identifier = definition.identifier,
                            referenceType = ReferenceType.full)
                else:
                    yield node

            elif isinstance(node, ImageReferenceNode):
                if node.identifier in definitions:
                    definition = definitions[node.identifier]
                    data_url = as_data_url(definition.url, base_path)

                    if data_url:
                        # Replace the original definition because we can't have
                        # definitions which point to other definitions.  On the
                        # second pass, we'll filter out the original and emit
                        # the new one at the bottom of the document.
                        definitions[definition.identifier] = (
                            DefinitionNode(
                                label = definition.label,
                                identifier = definition.identifier,
                                url = data_url))

                # Always yield the original image reference since the
                # identifier is unchanged.
                yield node

            elif isinstance(node, CodeNode) and node.lang == "auspiceMainDisplayMarkdown":
                # Recursively embed images inside the main display content too
                yield CodeNode(
                    lang  = node.lang,
                    meta  = node.meta,
                    value = generate(embed_images(parse(node.value), base_path)))

            else:
                yield node

    nodes = list(first_pass(nodes))

    # Second pass to drop replaced definitions and add new ones at the end,
    # sequestering the long data: URLs to the bottom of the document.
    to_drop = [d for d in original_definitions.values() if d not in definitions.values()]
    to_add  = [d for d in definitions.values() if d not in original_definitions.values()]

    def second_pass(nodes: NodeList) -> Generator[NodeListNode, None, None]:
        yield from (n for n in nodes if n not in to_drop)
        yield "\n\n"
        for n in reversed(to_add): # reversed() to undo the original reversed() above
            yield n
            yield "\n"

    nodes = list(second_pass(nodes))

    return nodes


def as_data_url(url: str, base_path: Path) -> Optional[str]:
    """
    Convert *url* to a ``data:`` URL if it refers to a local file (potentially
    relative to *base_path*).

    *url* must be a bare path (e.g. ``a/b/c.png``) or a ``file:`` URL without a
    hostname part (e.g. ``file:///a/b/c.png``).

    Returns ``None`` if *url* doesn't refer to a local file (or the file
    doesn't exist).
    """
    url_ = urlsplit(url)

    # Must be a bare path or a file:///path URL
    if (url_.scheme, url_.netloc) not in {("", ""), ("file", "")}:
        return None

    file = base_path / url_.path

    # Whelp, the file's missing, but there's nothing we can do about it.
    if not file.exists():
        # XXX TODO: issue a warning?
        return None

    content = urlquote(b64encode(file.read_bytes()).decode("utf-8"))
    content_type, _ = mimetypes.guess_type(file.name)

    if not content_type:
        content_type = "application/octet-stream"

    return f"data:{content_type};base64,{content}"


def normalize_label(label: str) -> str:
    """
    Per the `mdast spec for an Association <https://github.com/syntax-tree/mdast#association>`__:

        To normalize a value, collapse markdown whitespace (``[\\t\\n\\r ]+``)
        to a space, trim the optional initial and/or final space, and perform
        case-folding.
    """
    return re.sub(r'[\t\n\r ]+', ' ', label).strip(" ").casefold()


def reference_type(label: str) -> ReferenceType:
    """
    Per the `mdast spec for a ReferenceType <https://github.com/syntax-tree/mdast#referencetype>`__::

        ![alt][label]  a "full" reference
        ![alt][]       a "collapsed" reference
        ![alt]         a "shortcut" reference
    """
    return (
        ReferenceType.shortcut  if label is None else
        ReferenceType.collapsed if not label     else
        ReferenceType.full
    )

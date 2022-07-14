"""
reStructuredText conversion.

.. envvar:: NEXTSTRAIN_RST_STRICT

    If set to any value, then rST parsing is put into strict mode and any
    warnings and errors are raised as exceptions.

.. envvar:: NEXTSTRAIN_RST_DEBUG

    If set to any value, then rST parsing produces the stringified doctree
    instead of formatted plain text.  Being able to see the doctree is useful
    for debugging and making changes to
    :cls:`~nextstrain.cli.rst.sphinx.TextWriter`.
"""
import docutils.nodes
import docutils.readers.standalone
import docutils.transforms
import os
import re
from docutils.core import publish_string as convert_rst_to_string, publish_doctree as convert_rst_to_doctree   # type: ignore
from docutils.parsers.rst.roles import register_local_role
from docutils.utils import unescape                         # type: ignore
from ..__version__ import __version__ as cli_version
from .sphinx import TextWriter


# For dev
DEBUG = os.environ.get("NEXTSTRAIN_RST_DEBUG", "") != ""

# For CI testing
STRICT = os.environ.get("NEXTSTRAIN_RST_STRICT", "") != ""

# Ignore rST issues by default as we don't want messages included in output or
# errors thrown at runtime.  Just do our best to convert.
REPORT_LEVEL_WARNINGS = 2
REPORT_LEVEL_NONE = 5
REPORT_LEVEL = REPORT_LEVEL_WARNINGS if STRICT else REPORT_LEVEL_NONE

ROLES_REGISTERED = False

PREAMBLE = """
.. default-role:: literal
"""

POSTAMBLE = """
.. target-notes::
"""


def rst_to_text(source: str) -> str:
    """
    Converts rST *source* to plain text.

    Standard Docutils directives, roles, etc. are all supported, along with the
    following additions:

        * ``:doc:`` reference roles, which resolve to absolute URL references.
        Automatic title expansion (e.g. like Sphinx's ``:doc:`` role) is not
        supported.  Intersphinx-like project identifiers may be used as
        prefixes, if configured in :func:`doc_url`.

    Sphinx directives, roles, etc. are not supported.

    The default role is ``literal`` instead of ``title-reference``.

    If conversion fails, *source* is returned.  Set
    :envvar:`NEXTSTRAIN_RST_STRICT` to enable strict conversion and raise
    exceptions for failures.
    """
    global ROLES_REGISTERED
    if not ROLES_REGISTERED:
        register_local_role("doc", doc_reference_role)
        ROLES_REGISTERED = True

    settings = {
        # Use Unicode strings for I/O, not encoded bytes.
        "input_encoding": "unicode",
        "output_encoding": "unicode",

        # Never halt midway, just keep going.
        "halt_level": REPORT_LEVEL_NONE,
        "report_level": REPORT_LEVEL,
        "exit_status_level": REPORT_LEVEL,
    }

    try:
        return convert_rst(
            "\n".join([PREAMBLE, source, POSTAMBLE]),
            reader = Reader(),
            writer = TextWriter(),
            settings_overrides = settings,
            enable_exit_status = STRICT)
    except:
        if STRICT:
            raise
        else:
            # Welp, we tried.  Return the rST input as a last resort.
            return source


def convert_rst(source: str, *, reader, writer, settings_overrides: dict, enable_exit_status: bool) -> str:
    if DEBUG:
        return str(
            convert_rst_to_doctree(
                source,
                reader = reader,
                settings_overrides = settings_overrides,
                enable_exit_status = enable_exit_status))

    return convert_rst_to_string(
        source,
        reader = reader,
        writer = writer,
        settings_overrides = settings_overrides,
        enable_exit_status = enable_exit_status)


# See docutils.parsers.rst.roles for this API and examples.
def doc_reference_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    """
    Docutils role handler for ``:doc:`` references.

    Handles the forms::

        :doc:`foo/bar`
        :doc:`other-project:foo/bar`
        :doc:`title <foo/bar>`
        :doc:`title <other-project:foo/bar>`
    """
    # Regexp based on one from sphinx.util.docutils.ReferenceRole.
    #
    # \x00 is a docutils escaping that means the "<" was backslash-escaped in rawtext.
    explicit_title = re.compile(r'^(?P<title>.+?)\s*(?<!\x00)<(?P<target>.*?)>$', re.DOTALL)

    matched = explicit_title.match(text)
    if matched:
        title  = unescape(matched["title"])
        target = unescape(matched["target"])
    else:
        title = None
        target = unescape(text)

    url = doc_url(target)

    return [docutils.nodes.reference(rawtext, title or url, refuri = url, **options)], []


def doc_url(target: str) -> str:
    """
    Construct the absolute URL for a ``:doc:`` *target*.

    The default project is the Nextstrain CLI, and the URLs produced will be
    version-specific so they stay relevant and accurate to what someone is
    running locally.

    *target* may be prefixed with a known project identifier (à la
    Intersphinx).

    If :envvar:`NEXTSTRAIN_RST_STRICT` is set, then an exception will be raised
    for an unknown project identifier in *target*.  Otherwise, *target* is
    returned as-is if unrecognized.
    """
    if ":" in target:
        project, path = target.split(":", 1)
    else:
        project, path = None, target

    project_urls = {
        None: (f"https://docs.nextstrain.org/projects/cli/en/{cli_version}/", ""),
        "docs": ("https://docs.nextstrain.org/page/", ".html"),
    }

    project_url, suffix = project_urls.get(project, (None, None))

    if STRICT:
        assert project_url is not None, f"unknown intersphinx id in :doc: target {target!r}"

    if not project_url:
        # Oh well.
        return target

    return project_url.rstrip("/") + "/" + path.lstrip("/") + suffix


class Reader(docutils.readers.standalone.Reader):
    def get_transforms(self):
        return [*super().get_transforms(), MarkEmbeddedHyperlinkReferencesAnonymous]


class MarkEmbeddedHyperlinkReferencesAnonymous(docutils.transforms.Transform):
    """
    Mark all hyperlink references with embedded targets as ``anonymous``.

    Hyperlink references with embedded targets [1]_ are syntactically always
    anonymous references [2]_, but the standard parser only marks them as
    anonymous if they refer to a separate anonymous target (i.e. don't embed
    the target using angle brackets) [3]_.  Presumably this is because such
    anonymous reference and anonymous target pairs need special processing that
    anonymous references with embedded targets don't [4]_.

    For our use, we want these embedded-target references to be picked up by
    the :cls:`docutils.transforms.references.TargetNotes` transform, which
    requires them to be marked anonymous.

    .. [1] https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#embedded-uris-and-aliases
    .. [2] https://docutils.sourceforge.io/docs/ref/rst/restructuredtext.html#anonymous-hyperlinks
    .. [3] https://sourceforge.net/p/docutils/code/HEAD/tree/trunk/docutils/docutils/parsers/rst/states.py#l859 (see phrase_ref() method)
    .. [4] See :cls:`docutils.transforms.references.AnonymousHyperlinks`.

    >>> rst_to_text('`foo <https://example.com/foo>`__')
    'foo [1]\\n\\n[1] https://example.com/foo\\n'

    >>> rst_to_text('''
    ... `bar <https://example.com/bar>`_
    ... `baz <bar_>`_
    ... ''')
    'bar [1] baz [1]\\n\\n[1] https://example.com/bar\\n'

    >>> rst_to_text('just a link, https://example.com/standalone, sitting right there')
    'just a link, https://example.com/standalone, sitting right there\\n'
    """

    # After other hyperlink reference processing, but before TargetNotes runs
    # and before other target processing removes "refname" attributes.  See:
    # https://docutils.sourceforge.io/docs/ref/transforms.html#transforms-listed-in-priority-order
    default_priority = 480

    def apply(self):
        for ref in self.document.traverse(docutils.nodes.reference):
            # Not embedded if it's got a refname, which refers to a target
            # name.
            if ref.get("refname"):
                continue

            # We only care about external (refuri) not internal (refid) links.
            if not ref.get("refuri"):
                continue

            # Skip standalone hyperlinks where the link text is the URL itself
            # since duplicating them in a footnote doesn't make much sense.
            if ref.get("refuri") == ref.astext().strip():
                continue

            # Some refs by this point will already be marked anonymous, but
            # there's no harm in marking "again".
            ref["anonymous"] = 1

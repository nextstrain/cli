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
import os
import re
from docutils.core import publish_string as convert_rst_to_string, publish_doctree as convert_rst_to_doctree   # type: ignore
from docutils.parsers.rst.roles import register_local_role
from docutils.utils import unescape                         # type: ignore
from urllib.parse import urljoin
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
            writer = TextWriter(),
            settings_overrides = settings,
            enable_exit_status = STRICT)
    except:
        if STRICT:
            raise
        else:
            # Welp, we tried.  Return the rST input as a last resort.
            return source


def convert_rst(source: str, *, writer, settings_overrides: dict, enable_exit_status: bool) -> str:
    if DEBUG:
        return str(
            convert_rst_to_doctree(
                source,
                settings_overrides = settings_overrides,
                enable_exit_status = enable_exit_status))

    return convert_rst_to_string(
        source,
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

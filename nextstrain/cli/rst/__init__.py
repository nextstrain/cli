"""
reStructuredText conversion.

.. envvar:: NEXTSTRAIN_RST_STRICT

    If set to any value, then rST parsing is put into strict mode and any
    warnings and errors are raised as exceptions.
"""
import os
from docutils.core import publish_string as convert_rst     # type: ignore
from .sphinx import TextWriter


# For CI testing
STRICT = os.environ.get("NEXTSTRAIN_RST_STRICT", "") != ""

# Ignore rST issues by default as we don't want messages included in output or
# errors thrown at runtime.  Just do our best to convert.
REPORT_LEVEL_WARNINGS = 2
REPORT_LEVEL_NONE = 5
REPORT_LEVEL = REPORT_LEVEL_WARNINGS if STRICT else REPORT_LEVEL_NONE

PREAMBLE = """
.. default-role:: literal

"""


def rst_to_text(source: str) -> str:
    """
    Converts rST *source* to plain text.

    Standard Docutils directives, roles, etc. are all supported.

    Sphinx directives, roles, etc. are not supported.

    The default role is ``literal`` instead of ``title-reference``.

    If conversion fails, *source* is returned.  Set
    :envvar:`NEXTSTRAIN_RST_STRICT` to enable strict conversion and raise
    exceptions for failures.
    """
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
            PREAMBLE + source,
            writer = TextWriter(),
            settings_overrides = settings,
            enable_exit_status = STRICT)
    except:
        if STRICT:
            raise
        else:
            # Welp, we tried.  Return the rST input as a last resort.
            return source

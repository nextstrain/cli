"""
Stub function and module used as a setuptools entry point.
"""

import sys
from io import TextIOWrapper
from sys import argv, exit
from nextstrain import cli

# Entry point for setuptools-installed script.
def main():
    # Explicitly configure our stdio output streams to be as assumed in the
    # rest of the codebase.  Avoids needing to instruct folks to set
    # PYTHONIOENCODING=UTF-8 or use Python's UTF-8 mode (-X utf8 or
    # PYTHONUTF8=1).
    sys.stdout = reconfigure_stdio(sys.stdout) # type: ignore[arg-type]
    sys.stderr = reconfigure_stdio(sys.stderr) # type: ignore[arg-type]

    return cli.run( argv[1:] )


def reconfigure_stdio(stdio: TextIOWrapper) -> TextIOWrapper:
    """
    Reconfigure *stdio* to match the assumptions of this codebase.

    Suitable only for output streams (e.g. stdout, stderr), as reconfiguring an
    input stream is more complicated.
    """
    # XXX TODO: When we drop Python 3.6 support, most of this function can be
    # replaced by stdio.reconfigure().
    #   -trs, 6 June 2022

    # Flush any pending output under old configuration.
    stdio.flush()

    # Configure new text stream on the same underlying buffered byte stream.
    return TextIOWrapper(
        stdio.buffer,

        # Always use UTF-8 and be more lenient on stderr so even mangled error
        # messages make it out.
        encoding = "UTF-8",
        errors = "backslashreplace" if stdio is sys.stderr else "strict",

        # Explicitly enable universal newlines mode so we do the right thing.
        newline = None,

        # Preserve line buffering which is set at process start dynamically
        # depending on what the stdio is actually attached to.
        line_buffering = stdio.line_buffering)


# Run when called as `python -m nextstrain.cli`, here for good measure.
if __name__ == "__main__":
    exit( main() )

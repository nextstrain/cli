"""
Prints the shell init script for a Nextstrain CLI standalone installation.

If PATH does not contain the expected installation path, emits an appropriate
``export PATH=…`` statement.  Otherwise, emits only a comment.

Use this command in your shell config with a line like the following::

    source <({INSTALLATION_PATH}/nextstrain init-shell)

Exits with error if run in an non-standalone installation.
"""

import os
import shutil
from pathlib import Path
from shlex import quote as shquote
from textwrap import dedent
from typing import Optional
from ..errors import UserError
from ..util import standalone_installation_path


try:
    INSTALLATION_PATH = standalone_installation_path()
except:
    INSTALLATION_PATH = None

# Guard against __doc__ being None to appease the type checkers.
__doc__ = (__doc__ or "").format(
    INSTALLATION_PATH = (
             shquote(str(INSTALLATION_PATH))
          if INSTALLATION_PATH
        else "…/path/to"
    )
)


def register_parser(subparser):
    parser = subparser.add_parser("init-shell", help = "Print shell init script")

    # We don't currently need to know this as we always emit POSIX shell.
    # Hedge against needing it in the future, though, by accepting it now so
    # people won't have to update their shell rcs later.
    parser.add_argument(
        "shell",
        help    = "Shell that's being initialized (e.g. bash, zsh, etc.); "
                  "currently we always emit POSIX shell syntax but this may change in the future.",
        nargs   = "?",
        default = "sh")

    return parser


def run(opts):
    if not INSTALLATION_PATH:
        raise UserError("No shell init required because this is not a standalone installation.")

    nextstrain = which("nextstrain")

    if not nextstrain or nextstrain.parent != INSTALLATION_PATH:
        if nextstrain:
            print(f"# This will mask {nextstrain}")
            print()

        # This risks duplication if INSTALLATION_PATH is already in PATH but
        # `nextstrain` is found on an earlier PATH entry.  A duplication-free
        # solution would be to detect that condition and *move* the existing
        # INSTALLATION_PATH entry in PATH to the front.  This is easy on the
        # face of it, so I started drafting an implementation before realizing
        # it's full of traps and adds lots of complexity, such as:
        #
        #   - Proper handling of original paths vs. resolved paths
        #     (e.g. symlinks, etc).  We'd need to match INSTALLATION_PATH on
        #     resolved paths but remove the original paths.
        #
        #   - Shell syntax for robustly filtering PATH.  Alternately, we could
        #     filter in Python and emit the static value instead of using $PATH.
        #     Both are unpleasant for the reason above.
        #
        # These are possible, but since this would all be for little gain in
        # what's already a edge case, let's not sweat it after all.
        #   -trs, 14 Sept 2022
        init = """
            # Add %(INSTALLATION_PATH)s to front of PATH
            export PATH=%(INSTALLATION_PATH)s"${PATH:+%(pathsep)s}$PATH"
        """
    else:
        init = """
            # PATH already finds this nextstrain at %(INSTALLATION_PATH)s
        """

    print(dedent(init.lstrip("\n")) % {
        "INSTALLATION_PATH": shquote(str(INSTALLATION_PATH)),
        "pathsep": os.pathsep
    })

    return 0


def which(cmd = "nextstrain") -> Optional[Path]:
    path = shutil.which(cmd)
    return Path(path).resolve(strict = True) if path else None

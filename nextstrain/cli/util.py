import os
import re
import requests
import subprocess
from types import ModuleType
from typing import List
from pkg_resources import parse_version
from sys import exit, stderr
from textwrap import dedent, indent
from .__version__ import __version__


def warn(*args):
    print(*args, file = stderr)


def colored(color, text):
    """
    Returns a string of text suitable for colored output on a terminal.
    """

    # These magic numbers are standard ANSI terminal escape codes for
    # formatting text.
    colors = {
        "red":    "\033[0;31m",
        "green":  "\033[0;32m",
        "blue":   "\033[0;1;34m",
        "yellow": "\033[0;33m",
        "gray":   "\033[0;90m",
        "bold":   "\033[1m",
        "reset":  "\033[0m",
    }

    return "{start}{text}{end}".format(
        start = colors.get(color, ""),
        end   = colors["reset"],
        text  = text,
    )


def remove_prefix(prefix, string):
    return re.sub('^' + re.escape(prefix), '', string)

def remove_suffix(suffix, string):
    return re.sub(re.escape(suffix) + '$', '', string)


def check_for_new_version():
    newer_version = new_version_available()

    if newer_version:
        print("A new version of nextstrain-cli, %s, is available!  You're running %s." % (newer_version, __version__))
        print()
        print("Upgrade by running:")
        print()
        print("    pip install --upgrade nextstrain-cli")
        print()
    else:
        print("nextstrain-cli is up to date!")
        print()

    return newer_version


def new_version_available():
    """
    Return the latest version of nextstrain-cli on PyPi if it's newer than the
    currently running version.  Otherwise return None.
    """
    this_version   = parse_version(__version__)
    latest_version = parse_version(fetch_latest_pypi_version("nextstrain-cli"))

    return latest_version if latest_version > this_version else None


def fetch_latest_pypi_version(project):
    """
    Return the latest version of the given project from PyPi.
    """
    return requests.get("https://pypi.python.org/pypi/%s/json" % project).json().get("info", {}).get("version", "")


def capture_output(argv):
    """
    Run the command specified by the argument list and return a list of output
    lines.

    This wrapper around subprocess.run() exists because its own capture_output
    parameter wasn't added until Python 3.7 and we aim for compat with 3.5.
    When we bump our minimum Python version, we can remove this wrapper.
    """
    result = subprocess.run(
        argv,
        stdout = subprocess.PIPE,
        check  = True)

    return result.stdout.decode("utf-8").splitlines()


def exec_or_return(argv: List[str]) -> int:
    """
    exec(3) into the desired program, or return 1 on failure.  Never returns if
    successful.

    The return value makes this suitable for chaining through to sys.exit().

    On Windows (or other non-POSIX OSs), where os.execvp() is not properly
    supported¹, this forks another process, waits for it to finish, and then
    exits with the same return code.  A proper POSIX exec(3) is still more
    desirable when available as it properly handles file descriptors and
    signals.

    ¹ https://bugs.python.org/issue9148
    """

    # Use a POSIX exec(3) for file descriptor and signal handling…
    if os.name == "posix":
        try:
            os.execvp(argv[0], argv)
        except OSError as error:
            warn("Error executing into %s: %s" % (argv, error))
            return 1

    # …or naively emulate one when not available.
    else:
        try:
            process = subprocess.run(argv)
        except OSError as error:
            warn("Error running %s: %s" % (argv, error))
            return 1
        else:
            exit(process.returncode)


def runner_name(runner: ModuleType) -> str:
    """
    Return a friendly name suitable for display for the given runner module.
    """
    return module_basename(runner).replace("_", "-")


def runner_help(runner: ModuleType) -> str:
    """
    Return a brief description of a runner module, suitable for help strings.
    """
    if runner.__doc__:
        return runner.__doc__.strip().splitlines()[0]
    else:
        return "(undocumented)"


def module_basename(module: ModuleType) -> str:
    """
    Return the final portion of the given module's name, akin to a file's basename.
    """
    return module.__name__.split(".")[-1]


def format_usage(doc: str) -> str:
    """
    Reformat a multi-line description of command-line usage to play nice with
    argparse's usage printing.

    Strips trailing and leading newlines, removes indentation shared by all
    lines (common in docstrings), and then pads all but the first line to match
    the "usage: " prefix argparse prints for the first line.
    """
    padding = " " * len("usage: ")
    return indent(dedent(doc.strip("\n")), padding).lstrip()

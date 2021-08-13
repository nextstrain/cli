import os
import re
import requests
import site
import subprocess
import sys
from types import ModuleType
from typing import Any, Mapping, List, Tuple
from pathlib import Path
from pkg_resources import parse_version
from shutil import which
from sys import exit, stderr, version_info as python_version
from textwrap import dedent, indent
from .__version__ import __version__
from .types import RunnerModule


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

    installed_into_user_site = \
            site.ENABLE_USER_SITE \
        and site.USER_SITE is not None \
        and __file__.startswith(site.USER_SITE)

    if sys.executable:
        exe_name = Path(sys.executable).name

        if which(exe_name) == sys.executable:
            python = exe_name
        else:
            python = sys.executable
    else:
        python = next(filter(which, ["python3", "python"])) or "python3"

    if newer_version:
        print("A new version of nextstrain-cli, %s, is available!  You're running %s." % (newer_version, __version__))
        print()
        print("Upgrade by running:")
        print()
        if "/pipx/venvs/nextstrain-cli/" in python:
            print("    pipx upgrade nextstrain-cli")
        else:
            print("    " + python + " -m pip install --user --upgrade nextstrain-cli" if installed_into_user_site else \
                  "    " + python + " -m pip install --upgrade nextstrain-cli")
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
    parameter wasn't added until Python 3.7 and we aim for compat with 3.6.
    When we bump our minimum Python version, we can remove this wrapper.
    """
    result = subprocess.run(
        argv,
        stdout = subprocess.PIPE,
        check  = True)

    return result.stdout.decode("utf-8").splitlines()


def exec_or_return(argv: List[str], extra_env: Mapping = {}) -> int:
    """
    exec(3) into the desired program, or return 1 on failure.  Never returns if
    successful.

    The return value makes this suitable for chaining through to sys.exit().

    On Windows (or other non-POSIX OSs), where os.execvp() is not properly
    supported¹, this forks another process, waits for it to finish, and then
    exits with the same return code.  A proper POSIX exec(3) is still more
    desirable when available as it properly handles file descriptors and
    signals.

    If an *extra_env* mapping is passed, the provided keys and values are
    overlayed onto the current environment.

    ¹ https://bugs.python.org/issue9148
    """
    env = os.environ.copy()

    if extra_env:
        env.update(extra_env)

    # Use a POSIX exec(3) for file descriptor and signal handling…
    if os.name == "posix":
        try:
            os.execvpe(argv[0], argv, env)
        except OSError as error:
            warn("Error executing into %s: %s" % (argv, error))
            return 1

    # …or naively emulate one when not available.
    else:
        try:
            process = subprocess.run(argv, env = env)
        except OSError as error:
            warn("Error running %s: %s" % (argv, error))
            return 1
        else:
            exit(process.returncode)


def runner_name(runner: RunnerModule) -> str:
    """
    Return a friendly name suitable for display for the given runner module.
    """
    return module_basename(runner).replace("_", "-")


def runner_help(runner: RunnerModule) -> str:
    """
    Return a brief description of a runner module, suitable for help strings.
    """
    if runner.__doc__:
        return runner.__doc__.strip().splitlines()[0]
    else:
        return "(undocumented)"


def module_basename(module: Any) -> str:
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


def resolve_path(path: Path) -> Path:
    """
    Resolves the given *path* **strictly**, throwing a
    :class:`FileNotFoundError` if it is not resolvable.

    This function exists only because Path.resolve()'s default behaviour
    changed from strict to not strict in 3.5 → 3.6.  In most places we want the
    strict behaviour, but the "strict" keyword argument didn't exist until 3.6
    when the behaviour became optional (and not the default).

    All this function does is call ``path.resolve()`` on 3.5 and
    ``path.resolve(strict = True)`` on 3.6.
    """
    if python_version >= (3,6):
        # mypy doesn't know we did a version check
        return path.resolve(strict = True) # type: ignore
    else:
        return path.resolve()


def byte_quantity(quantity: str) -> int:
    """
    Parses a string *quantity* consisting of a number, optional whitespace, and
    a unit of bytes.

    Returns the number of bytes in *quantity*, as an integer.

    Supported units:

    * ``b`` (bytes)
    * ``kb`` (kilobytes)
    * ``mb`` (megabytes)
    * ``gb`` (gigabytes)
    * ``kib`` (kibibytes)
    * ``mib`` (mebibytes)
    * ``gib`` (gibibytes)

    Units are not case sensitive.  If no unit is given, bytes is assumed.

    Raises a :py:class:`ValueError` if *quantity* is not parseable.

    >>> byte_quantity("2Kb")
    2000
    >>> byte_quantity("2 kib")
    2048
    >>> byte_quantity("1.5GB")
    1500000000
    >>> byte_quantity("1024")
    1024
    >>> byte_quantity("hello mb")
    Traceback (most recent call last):
        ...
    ValueError: Unparseable byte quantity value: 'hello'
    """
    match = re.search(r"""
        ^
        # The numeric value.  We rely on float() to parse this, so don't
        # restrict it here.
        (\S+?)

        \s*

        # The optional unit.
        ( [kmg]b
        | [kmg]ib
        | b
        )?
        $
        """, quantity.strip(), re.VERBOSE | re.IGNORECASE)

    if not match:
        raise ValueError("Unrecognized byte quantity: %s" % repr(quantity))

    value_str, units = match.groups()

    try:
        value = float(value_str)
    except ValueError:
        raise ValueError("Unparseable byte quantity value: %s" % repr(value_str)) from None

    if not units:
        units = "b"

    unit_factor = {
        'b': 1,
        'kb': 1000,
        'mb': 1000**2,
        'gb': 1000**3,
        'kib': 1024,
        'mib': 1024**2,
        'gib': 1024**3,
    }

    return int(value * unit_factor[units.lower()])


def split_image_name(name: str) -> Tuple[str, str]:
    """
    Split the Docker image *name* into a (repository, tag) tuple.

    >>> split_image_name("nextstrain/base:build-20200424T101900Z")
    ('nextstrain/base', 'build-20200424T101900Z')

    >>> split_image_name("nextstrain/base")
    ('nextstrain/base', 'latest')
    """
    if ":" in name:
        repository, tag = name.split(":", maxsplit = 2)
    else:
        repository, tag = name, "latest"

    return (repository, tag)

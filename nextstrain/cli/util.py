import os
import re
import requests
import subprocess
from types import ModuleType
from pkg_resources import parse_version
from sys import stderr
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


def exec_or_return(argv):
    """
    exec(3) into the desired program, or return 1 on failure.  Never returns if
    successful.

    The return value makes this suitable for chaining through to sys.exit().
    """
    try:
        os.execvp(argv[0], argv)
    except OSError as error:
        warn("Error executing into %s: %s" % (argv, error))
        return 1


def runner_name(runner: ModuleType) -> str:
    """
    Return a friendly name suitable for display for the given runner module.
    """
    return module_basename(runner).replace("_", "-")


def module_basename(module: ModuleType, base_module: str = None) -> str:
    """
    Return the final portion of the given module's name, akin to a file's basename.

    Defaults to returning the portion after the name of the module's containing
    package, but this may be changed by providing the base_module parameter.
    """
    if not base_module:
        base_module = module.__package__

    return remove_prefix(base_module, module.__name__).lstrip(".")

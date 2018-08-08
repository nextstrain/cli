import re
import requests
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

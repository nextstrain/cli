try:
    from importlib.metadata import distribution as distribution_info, PackageNotFoundError
except ModuleNotFoundError:
    from importlib_metadata import distribution as distribution_info, PackageNotFoundError

import os
import platform
import re
import requests
import site
import subprocess
import sys
from functools import partial
from typing import Any, Callable, Mapping, List, Optional, Sequence, Tuple, Union, overload
from typing_extensions import Literal
from packaging.version import parse as parse_version
from pathlib import Path
from shlex import quote as shquote
from shutil import which
from textwrap import dedent, indent
from wcmatch.glob import globmatch, GLOBSTAR, EXTGLOB, BRACE, MATCHBASE, NEGATE
from .__version__ import __version__
from .types import RunnerModule, RunnerTestResults


def warn(*args):
    print(*args, file = sys.stderr)


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
        and (__file__ or "").startswith(site.USER_SITE)

    # Find our Python executable/command.
    if sys.executable:
        exe_name = Path(sys.executable).name

        if which(exe_name) == sys.executable:
            python = exe_name
        else:
            python = sys.executable
    else:
        # We don't know our own executable, which is a bit unusual, so first
        # see if either python3 or python is available on PATH and use the
        # first one that is.  If neither is on PATH, use python3 and hope the
        # user can figure it out.
        python = next(filter(which, ["python3", "python"]), "python3")

    # Find our installer (e.g. pip, conda).
    try:
        distribution = distribution_info("nextstrain-cli")
    except PackageNotFoundError:
        installer = None
    else:
        installer = (distribution.read_text("INSTALLER") or '').strip() or None

    # Determine if we're pipx or not.
    if installer == "pip" and "/pipx/venvs/nextstrain-cli/" in python:
        installer = "pipx"

    # Find our Conda details, if applicable.
    if installer == "conda":
        # Prefer mamba over conda, if available on PATH.
        #
        # If we can't find either mamba or conda on the current PATH but we're
        # positively installed via a Conda package, then we have to assume that
        # a) one of them is available _somehow_ and b) that the user knows (or
        # will figure out) how to run one of them. We could default to either
        # conda or mamba, but since our official install instructions use mamba
        # and conda sometimes has dep-solving memory issues, I figured that
        # mamba was the best thing to use in this edge case.
        #
        # There's several reasons why neither command may be available on PATH
        # when we go looking with `which`, e.g. the commands could be off PATH
        # but available via shell alias or shell function wrappers or they
        # could be behind a modules system like Environment Modules and need
        # enabling with e.g. `module load …`.
        #   -trs, 28 July 2022
        conda = next(filter(which, ["mamba", "conda"]), "mamba")

        # Search upwards for first parent directory which contains a
        # "conda-meta" dir.  This is the env prefix.
        parent_dirs = Path(__file__).resolve(strict = True).parents
        conda_prefix = next((str(d) for d in parent_dirs if (d / "conda-meta").is_dir()), None)
    else:
        conda, conda_prefix = None, None

    # Put it all together into an upgrade command!
    if newer_version:
        pkgreq = shquote(f"nextstrain-cli=={newer_version}")

        print("A new version of nextstrain-cli, %s, is available!  You're running %s." % (newer_version, __version__))
        print()
        print("See what's new in the changelog:")
        print()
        print(f"    https://github.com/nextstrain/cli/blob/{newer_version}/CHANGES.md#readme")
        print()

        if standalone_installation():
            print("Upgrade your standalone installation by running:")
            print()
            print(f"    {standalone_installer(newer_version)}")
            print()
            print("or by downloading a new archive from:")
            print()
            print(f"    {standalone_installation_archive_url(newer_version)}")

        elif installer == "pip":
            print("Upgrade your Pip-based installation by running:")
            print()
            print(f"    {python} -m pip install --user {pkgreq}" if installed_into_user_site else \
                  f"    {python} -m pip install {pkgreq}")

        elif installer == "pipx":
            print("Upgrade your pipx-based installation by running:")
            print()
            print(f"    pipx install -f {pkgreq}")

        elif installer == "conda":
            print("Upgrade your Conda-based installation running:")
            print()
            if conda_prefix:
                print(f"    {conda} install -p {shquote(conda_prefix)} {pkgreq}")
            else:
                print(f"    {conda} install {pkgreq}   # add -n NAME or -p PATH if necessary")

        else:
            print(f"(Omitting tailored instructions for upgrading due to unknown installation method ({installer!r}).)")

        print()
    else:
        print("nextstrain-cli is up to date!")
        print()

    return newer_version


def standalone_installation():
    """
    Return True if this is a standalone installation, i.e. a self-contained
    executable built with PyOxidizer.

    Relies on a compiled-in -X flag set at build time by our PyOxidizer config.
    """
    # sys._xoptions is documented for use but specific to CPython.  Our
    # standalone executables are built upon CPython, so this works in that
    # context, but this code may also run on other interpreters (e.g. PyPy) in
    # other contexts.
    #
    # I think using an explicit, compiled-in flag is best, but we could
    # alternatively choose to inspect something like:
    #
    #     nextstrain.cli.__loader__.__module__ == "oxidized_importer"
    #
    # if necessary in the future.
    #   -trs, 7 July 2022
    return "nextstrain-cli-is-standalone" in getattr(sys, "_xoptions", {})


def standalone_installation_path() -> Optional[Path]:
    """
    Return the path of this standalone installation, if applicable.
    """
    if not standalone_installation():
        return None

    if not sys.executable:
        return None

    return Path(sys.executable).resolve(strict = True).parent


def standalone_installer(version: str) -> str:
    system = platform.system()

    if system == "Linux":
        return f"curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/linux | bash -s {shquote(version)}"

    elif system == "Darwin":
        return f"curl -fsSL --proto '=https' https://nextstrain.org/cli/installer/mac | bash -s {shquote(version)}"

    elif system == "Windows":
        return 'Invoke-Expression "& { $(Invoke-RestMethod https://nextstrain.org/cli/installer/windows) } %s"' % shquote(version)

    else:
        raise RuntimeError(f"unknown system {system!r}")


def standalone_installation_archive_url(version: str) -> str:
    machine = platform.machine()
    system = platform.system()

    if system == "Linux":
        vendor, os, archive_format = "unknown", "linux-gnu", "tar.gz"
    elif system == "Darwin":
        vendor, os, archive_format = "apple", "darwin", "tar.gz"
    elif system == "Windows":
        vendor, os, archive_format = "pc", "windows-msvc", "zip"
    else:
        raise RuntimeError(f"unknown system {system!r}")

    target_triple = f"{machine}-{vendor}-{os}"

    return f"https://nextstrain.org/cli/download/{version}/standalone-{target_triple}.{archive_format}"


def new_version_available():
    """
    Return the latest version of nextstrain-cli on PyPI if it's newer than the
    currently running version.  Otherwise return None.

    .. envvar:: NEXTSTRAIN_CLI_LATEST_VERSION

        If set, the value will be used as the latest released version of
        nextstrain-cli and the query to PyPI will be skipped.  Primarily
        intended for development and testing but can also be used to disable
        the update check by setting the value to 0.
    """
    this_version   = parse_version(__version__)
    latest_version = parse_version(os.environ.get("NEXTSTRAIN_CLI_LATEST_VERSION") or fetch_latest_pypi_version("nextstrain-cli"))

    return str(latest_version) if latest_version > this_version else None


def fetch_latest_pypi_version(project):
    """
    Return the latest version of the given project from PyPi.
    """
    return requests.get("https://pypi.python.org/pypi/%s/json" % project).json().get("info", {}).get("version", "")


def capture_output(argv, extra_env: Mapping = {}):
    """
    Run the command specified by the argument list and return a list of output
    lines.

    This wrapper around subprocess.run() exists because its own capture_output
    parameter wasn't added until Python 3.7 and we aim for compat with 3.6.
    When we bump our minimum Python version, we can remove this wrapper.

    If an *extra_env* mapping is passed, the provided keys and values are
    overlayed onto the current environment.
    """
    env = os.environ.copy()

    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        argv,
        env    = env,
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
            sys.exit(process.returncode)


def runner_name(runner: RunnerModule) -> str:
    """
    Return a friendly name suitable for display for the given runner module.
    """
    return module_basename(runner).replace("_", "-")


def runner_module(name: str) -> RunnerModule:
    """
    Converts a string *name* into a :py:cls:`RunnerModule`.

    *name* is case-insensitive and underscores, hyphens, or spaces may be used
    to separate words.  Internally, they're normalized to hyphens and the whole
    string is lowercased.

    ``native`` is accepted as an alias for ``ambient``.

    Raises a :py:exc:`ValueError` if *name* is unknown.

    >>> runner_module("docker") # doctest: +ELLIPSIS
    <module 'cli.runner.docker' from '...'>

    >>> runner_module("AWS-Batch") # doctest: +ELLIPSIS
    <module 'cli.runner.aws_batch' from '...'>

    >>> runner_module("AWS Batch") # doctest: +ELLIPSIS
    <module 'cli.runner.aws_batch' from '...'>

    >>> runner_module("native") # doctest: +ELLIPSIS
    <module 'cli.runner.ambient' from '...'>

    >>> runner_module("invalid")
    Traceback (most recent call last):
        ...
    ValueError: invalid runtime name: 'invalid'; valid names are: 'docker', 'conda', 'singularity', 'ambient', 'aws-batch'

    >>> runner_module("Invalid Name")
    Traceback (most recent call last):
        ...
    ValueError: invalid runtime name: 'Invalid Name' (normalized to 'invalid-name'); valid names are: 'docker', 'conda', 'singularity', 'ambient', 'aws-batch'
    """
    # Import here to avoid circular import
    from .runner import all_runners_by_name

    normalized_name = re.sub(r'(_|\s+)', '-', name).lower()

    # Accept "native" as an alias for "ambient" for backwards compatibility
    if normalized_name == "native":
        normalized_name = "ambient"

    try:
        return all_runners_by_name[normalized_name]
    except KeyError as err:
        valid_names = ", ".join(map(repr, all_runners_by_name))

        if name != normalized_name:
            raise ValueError(f"invalid runtime name: {name!r} (normalized to {normalized_name!r}); valid names are: {valid_names}") from err
        else:
            raise ValueError(f"invalid runtime name: {name!r}; valid names are: {valid_names}") from err


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


@overload
def split_image_name(name: str, implicit_latest: Literal[True] = True) -> Tuple[str, str]:
    ...

@overload
def split_image_name(name: str, implicit_latest: Literal[False]) -> Tuple[str, Optional[str]]:
    ...

def split_image_name(name: str, implicit_latest: bool = True) -> Tuple[str, Optional[str]]:
    """
    Split the Docker image *name* into a (repository, tag) tuple.

    >>> split_image_name("nextstrain/base:build-20200424T101900Z")
    ('nextstrain/base', 'build-20200424T101900Z')

    >>> split_image_name("nextstrain/base")
    ('nextstrain/base', 'latest')

    >>> split_image_name("nextstrain/base", implicit_latest = False)
    ('nextstrain/base', None)

    >>> split_image_name("nextstrain/base:latest", implicit_latest = False)
    ('nextstrain/base', 'latest')
    """
    if ":" in name:
        repository, tag = name.split(":", maxsplit = 2)
    else:
        repository, tag = name, "latest" if implicit_latest else None

    return (repository, tag)


def glob_matcher(patterns: Sequence[str]) -> Callable[[Union[str, Path]], bool]:
    """
    Generate a function which matches a string or path-like object against the
    list of Bash-like glob *patterns*.

    See :func:`glob_match` for supported pattern features.
    """
    def matcher(path: Union[str, Path]) -> bool:
        return glob_match(path, patterns)

    return matcher


def glob_match(path: Union[str, Path], patterns: Union[str, Sequence[str]]) -> bool:
    """
    Test if *path* matches any of the glob *patterns*.

    Besides basic glob features like single-part wildcards (``*``), character
    classes (``[…]``), and brace expansion (``{…, …}``), several advanced
    globbing features are also supported: multi-part wildcards (``**``),
    extended globbing (``@(…)``, ``+(…)``, etc.), basename matching for
    patterns containing only a single path part, and negation (``!…``).

    Implemented with with :func:`wcmatch.glob.globmatch`.
    """
    return globmatch(path, patterns, flags = GLOBSTAR | BRACE | EXTGLOB | MATCHBASE | NEGATE)


def runner_tests_ok(tests: RunnerTestResults) -> bool:
    """
    Returns True iff none of a runner's ``test_setup()`` results failed.
    """
    return False not in [result for test, result in tests]


def print_runner_tests(tests: RunnerTestResults):
    """
    Prints a formatted version of the return value of a runner's
    ``test_setup()``.
    """
    success = partial(colored, "green")
    failure = partial(colored, "red")
    warning = partial(colored, "yellow")
    unknown = partial(colored, "gray")

    # XXX TODO: Now that there are special values other than True/False, these
    # should probably become an enum or custom algebraic type or something
    # similar.  That will cause a cascade into the test_setup() producers
    # though, which I'm going to punt on for now.
    #  -trs, 4 Oct 2018
    status = {
        True:  success("✔ yes"),
        False: failure("✘ no"),
        None:  warning("⚑ warning"),
        ...:   unknown("? unknown"),
    }

    for description, result in tests:
        # Indent subsequent lines of any multi-line descriptions so it
        # lines up under the status marker.
        formatted_description = \
            remove_prefix("  ", indent(description, "  "))

        print(status.get(result, str(result)) + ":", formatted_description)

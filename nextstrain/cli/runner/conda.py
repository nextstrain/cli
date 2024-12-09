"""
Run commands with access to a fully-managed Conda environment.

`Conda <https://docs.conda.io/en/latest/miniconda.html>`__ is a very popular
packaging system freely-available for all platforms. When you use Nextstrain
CLI's built-in Conda support, you don't need to install any other Nextstrain
software dependencies yourself as validated versions are already bundled into a
package (`nextstrain-base`_) by the Nextstrain team and automatically managed
in an isolated location (isolated even from other Conda environments you may
manage yourself).

.. _nextstrain-base: https://github.com/nextstrain/conda-base


.. versionadded:: 5.0.0


.. _conda-setup:

Setup
=====

On macOS and Linux, run ``nextstrain setup conda`` to get started.

This will download compressed packages totaling about 450 MB in size which
expand to a final on-disk size of about 2 GB.  Transient disk usage during this
process peaks at about 3 GB.  These numbers are current as of August 2023, as
observed on Linux.  Numbers will vary over time, with a tendency to slowly
increase, and vary slightly by OS.

This runtime is not directly supported on Windows, but you can use `WSL2
<https://docs.microsoft.com/en-us/windows/wsl/wsl2-index>`__ to "switch" to
Linux and run the above setup command.


.. _conda-env:

Environment variables
=====================

.. warning::
    For development only.  You don't need to set these during normal operation.

.. envvar:: NEXTSTRAIN_CONDA_CHANNEL

    Conda channel name (or URL) to use for Nextstrain packages not otherwise
    available via Bioconda (e.g. ``nextstrain-base``).

    Defaults to ``nextstrain``.

.. envvar:: NEXTSTRAIN_CONDA_BASE_PACKAGE

    Conda meta-package name to use for the Nextstrain base runtime dependencies.

    May be a two- or three-part `Conda package match spec`_ instead of just a
    package name.  Note that a ``conda install``-style package spec, with a
    single ``=`` or without spaces, is not supported.

    Defaults to ``nextstrain-base``.

    .. _Conda package match spec: https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html#package-match-specifications

.. envvar:: NEXTSTRAIN_CONDA_MICROMAMBA_VERSION

    Version of Micromamba to use for setup and upgrade of the Conda runtime
    env.  Must be a version available from the `conda-forge channel
    <https://anaconda.org/conda-forge/micromamba/>`__, or the special string
    ``latest``.

    Defaults to ``1.5.8``.
"""

import json
import os
import platform
import re
import requests
import shutil
import subprocess
import tarfile
import traceback
from pathlib import Path, PurePosixPath
from typing import Iterable, NamedTuple, Optional
from urllib.parse import urljoin, quote as urlquote
from ..errors import InternalError
from ..paths import RUNTIMES
from ..types import Env, RunnerSetupStatus, RunnerTestResults, RunnerUpdateStatus
from ..util import capture_output, colored, exec_or_return, parse_version_lax, runner_tests_ok, test_rosetta_enabled, warn


RUNTIME_ROOT = RUNTIMES / "conda/"

PREFIX     = RUNTIME_ROOT / "env/"
PREFIX_BIN = PREFIX / "bin"

MICROMAMBA_ROOT = RUNTIME_ROOT / "micromamba/"
MICROMAMBA      = MICROMAMBA_ROOT / "bin/micromamba"

# If you update the version pin below, please update the docstring above too.
MICROMAMBA_VERSION = os.environ.get("NEXTSTRAIN_CONDA_MICROMAMBA_VERSION") \
                  or "1.5.8"

NEXTSTRAIN_CHANNEL = os.environ.get("NEXTSTRAIN_CONDA_CHANNEL") \
                  or "nextstrain"

NEXTSTRAIN_BASE = os.environ.get("NEXTSTRAIN_CONDA_BASE_PACKAGE") \
               or "nextstrain-base"

PYTHONUSERBASE = RUNTIME_ROOT / "python-user-base"

# Construct a PATH with our runtime prefix which provides some, but not total,
# isolation from the rest of the system.
PATH = os.pathsep.join(map(str, [
    # Programs installed by this runtime.
    PREFIX_BIN,

    # Python's idea of a default path for the system, which currently under
    # CPython is either "/bin:/usr/bin" on POSIX systems or ".;C:\\bin" on
    # Windows.  This will ensure basic system commands like `ls` are
    # available, although it will also "leak" any user-installed programs
    # there.
    os.defpath,
]))

EXEC_ENV = {
    "PATH": PATH,

    # Avoid letting user-set custom Python installs and module search paths
    # from outside the runtime leak inside.
    "PYTHONHOME": None,
    "PYTHONPATH": None,

    # Avoid letting the user site directory leak into the runtime, c.f.
    # <https://docs.python.org/3/library/site.html> and
    # <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONNOUSERSITE>.
    "PYTHONUSERBASE": str(PYTHONUSERBASE),
    "PYTHONNOUSERSITE": "1",
}


def register_arguments(parser) -> None:
    """
    No-op.  No arguments necessary.
    """
    pass


def run(opts, argv, working_volume = None, extra_env: Env = {}, cpus: int = None, memory: int = None) -> int:
    if working_volume:
        os.chdir(str(working_volume.src))

    # XXX TODO: In the future we might want to set rlimits based on cpus and
    # memory, at least on POSIX systems.
    #   -trs, 21 May 2020 (copied from ./native.py on 30 Aug 2022)

    # XXX TODO: If we need to support Conda activation scripts (e.g.
    # …/env/etc/conda/activate.d/) in the future, we could probably switch to
    # exec chaining thru `micromamba run` here (with carefully constructed
    # options and environ akin to what we do in micromamba() below).
    #
    # Currently our env has a couple activation scripts, but they're not
    # necessary due to 1) our particular usage of the related packages and 2)
    # that this runtime, for reasons of package availability, can't support
    # Windows at this time (where activation is more crucial than Unix due to
    # DLL searching).
    #   -trs, 13 Jan 2023

    return exec_or_return(argv, {**extra_env, **EXEC_ENV})


def setup(dry_run: bool = False, force: bool = False) -> RunnerSetupStatus:
    if not setup_micromamba(dry_run, force):
        return False

    if not setup_prefix(dry_run, force):
        return False

    return True


def setup_micromamba(dry_run: bool = False, force: bool = False) -> bool:
    """
    Install Micromamba into our ``MICROMAMBA_ROOT``.
    """
    if not force and MICROMAMBA.exists():
        print(f"Using existing Micromamba installation at {MICROMAMBA_ROOT}.")
        print(f"  Hint: if you want to ignore this existing installation, re-run `nextstrain setup` with --force.")
        return True

    if MICROMAMBA_ROOT.exists():
        print(f"Removing existing directory {MICROMAMBA_ROOT} to start fresh…")
        if not dry_run:
            shutil.rmtree(str(MICROMAMBA_ROOT))

    # Query for Micromamba release
    try:
        dist = package_distribution("conda-forge", "micromamba", MICROMAMBA_VERSION)
    except InternalError as err:
        warn(err)
        return False

    assert dist, f"unable to find micromamba dist"

    # download_url is scheme-less, so add our preferred scheme but in a way
    # that won't break if it starts including a scheme later.
    dist_url = urljoin("https:", dist["download_url"])

    print(f"Requesting Micromamba from {dist_url}…")

    if not dry_run:
        response = requests.get(dist_url, stream = True)
        response.raise_for_status()
        content_type = response.headers["Content-Type"]

        assert content_type == "application/x-tar", \
            f"unknown content-type for micromamba dist: {content_type}"

        with tarfile.open(fileobj = response.raw, mode = "r|*") as tar:
            # Ignore archive members starting with "/" and or including ".." parts,
            # as these can be used (maliciously or accidentally) to overwrite
            # unintended files (e.g. files outside of MICROMAMBA_ROOT).
            safe_members = (
                member
                    for member in tar
                     if not member.name.startswith("/")
                    and ".." not in PurePosixPath(member.name).parts)

            print(f"Downloading and extracting Micromamba to {MICROMAMBA_ROOT}…")
            tar.extractall(path = str(MICROMAMBA_ROOT), members = safe_members)
    else:
        print(f"Downloading and extracting Micromamba to {MICROMAMBA_ROOT}…")

    return True


def setup_prefix(dry_run: bool = False, force: bool = False) -> bool:
    """
    Install Conda packages with Micromamba into our ``PREFIX``.
    """
    if not force and (PREFIX_BIN / "augur").exists():
        print(f"Using existing Conda packages in {PREFIX}.")
        print(f"  Hint: if you want to ignore this existing installation, re-run `nextstrain setup` with --force.")
        return True

    if PREFIX.exists():
        print(f"Removing existing directory {PREFIX} to start fresh…")
        if not dry_run:
            shutil.rmtree(str(PREFIX))

    # We accept a package match spec, which one to three space-separated parts.¹
    # If we got a spec, then we use it as-is.
    #
    # ¹ <https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html#package-match-specifications>
    #
    if " " in NEXTSTRAIN_BASE.strip():
        install_spec = NEXTSTRAIN_BASE
    else:
        latest_version = (package_distribution(NEXTSTRAIN_CHANNEL, NEXTSTRAIN_BASE) or {}).get("version")

        if latest_version:
            install_spec = f"{NEXTSTRAIN_BASE} =={latest_version}"
        else:
            warn(f"Unable to find latest version of {NEXTSTRAIN_BASE} package; falling back to non-specific install")

            install_spec = NEXTSTRAIN_BASE

    # Create environment
    print(f"Installing Conda packages into {PREFIX}…")
    print(f"  - {install_spec}")

    if not dry_run:
        try:
            micromamba("create", install_spec)
        except InternalError as err:
            warn(err)
            traceback.print_exc()
            return False

    # Clean up unnecessary caches
    print("Cleaning up…")

    if not dry_run:
        try:
            micromamba("clean", "--all", add_prefix = False)
        except InternalError as err:
            warn(err)
            warn(f"Continuing anyway.")

    return True


def micromamba(*args, add_prefix: bool = True) -> None:
    """
    Runs our installed Micromamba with appropriate global options and options
    for prefix and channel selection.

    Invokes :py:func:`subprocess.run` and checks the exit status.  Raises a
    :py:exc:`InternalError` on failure, chained from the original
    :py:exc:`OSError` or :py:exc:`subprocess.CalledProcessError`.

    For convenience, all arguments are converted to strings before being passed
    to :py:func:`subprocess.run`.

    Set the keyword-only argument *add_prefix* to false to omit the
    ``--prefix`` option and channel-related options which are otherwise
    automatically added.
    """
    argv = tuple(map(str, (
        MICROMAMBA,

        # Always use our custom root
        "--root-prefix", MICROMAMBA_ROOT,

        # Ignore any config the user may have set
        "--no-rc",
        "--no-env",

        # Never prompt
        "--yes",

        *args,
    )))

    if add_prefix:
        argv += (
            # Path-based env
            "--prefix", str(PREFIX),

            # BioConda config per <https://bioconda.github.io/#usage>, plus our
            # own channel.
            "--override-channels",
            "--strict-channel-priority",
            "--channel", NEXTSTRAIN_CHANNEL,
            "--channel", "conda-forge",
            "--channel", "bioconda",

            # Don't automatically pin Python so nextstrain-base deps can change
            # it on upgrade.
            "--no-py-pin",

            # Allow uninstalls and downgrades of existing installed packages so
            # nextstrain-base deps can change on upgrade.  Uninstalls are
            # currently allowed by default (unlike downgrades), but make it
            # explicit here.
            "--allow-uninstall",
            "--allow-downgrade",
        )

    env = {
        # Filter out all CONDA_* and MAMBA_* host env vars so micromamba's
        # behaviour isn't affected by running inside an externally-activated
        # Conda environment (CONDA_*) or user-set configuration vars (MAMBA_*).
        #
        # When first drafting this runner, I'd thought we might have to do this
        # env filtering, but everything seemed to work fine in practice without
        # it, so I didn't on the premise of not including code you don't need.
        # Joke's on me!  Now that I've been burned by CONDA_PROMPT_MODIFIER
        # triggering an infinite loop in the right conditions¹, let's be
        # proactively defensive and filter them all out.
        #
        # We bother with MAMBA_* vars even though we're using --no-env above
        # because it turns out that Micromamba may sometimes indirectly invoke
        # itself (e.g. the generated wrapper script for package post-link
        # scripts calls `micromamba activate`).  We can't apply command-line
        # options to those instances, so use env vars.
        #   -trs, 7 Oct 2022
        #
        # ¹ <https://github.com/nextstrain/cli/pull/223#issuecomment-1270806302>
        **{ k: v
            for k, v in os.environ.copy().items()
             if not any(k.startswith(p) for p in {"CONDA_", "MAMBA_"}) },

        # Set env vars to match options above for subprocesses that micromamba
        # itself launches.  We can't include MAMBA_NO_ENV because that would
        # make these two vars moot, but we do filter out all other CONDA_* and
        # MAMBA_* vars above.
        "MAMBA_ROOT_PREFIX": str(MICROMAMBA_ROOT),
        "MAMBA_NO_RC": "true",

        # Override HOME so that micromamba's hardcoded paths under ~/.mamba/
        # don't get used.  This could lead to issues with a shared package
        # cache at ~/.mamba/pkgs/ for example.
        "HOME": str(RUNTIME_ROOT),
    }

    try:
        subprocess.run(argv, env = env, check = True)
    except (OSError, subprocess.CalledProcessError) as err:
        raise InternalError(f"Error running {argv!r}") from err


def test_setup() -> RunnerTestResults:
    def which_finds_our(cmd) -> bool:
        # which() checks executability and also handles PATHEXT, e.g. the
        # ".exe" extension on Windows, which is why we don't just naively test
        # for existence ourselves.  File extensions are also why we don't test
        # equality below instead check containment in PREFIX_BIN.
        found = shutil.which(cmd, path = PATH)

        if not found:
            return False

        # Path.is_relative_to() was added in Python 3.9, so implement it
        # ourselves around .relative_to().
        try:
            Path(found).relative_to(PREFIX_BIN)
        except ValueError:
            return False
        else:
            return True


    def runnable(*argv) -> bool:
        try:
            capture_output(argv, extra_env = EXEC_ENV)
            return True
        except (OSError, subprocess.CalledProcessError):
            return False


    support = list(test_support())

    yield from support

    if not runner_tests_ok(support):
        return

    elif not PREFIX_BIN.exists():
        yield ("runtime appears set up\n\n"
               "The Conda runtime appears supported but not yet set up.\n"
               "Try running `nextstrain setup conda` first.", False)

    else:
        yield ("runtime appears set up", True)

        yield ('snakemake is installed and runnable',
                which_finds_our("snakemake") and runnable("snakemake", "--version"))

        yield ('augur is installed and runnable',
                which_finds_our("augur") and runnable("augur", "--version"))

        yield ('auspice is installed and runnable',
                which_finds_our("auspice") and runnable("auspice", "--version"))


def test_support() -> RunnerTestResults:
    def supported_os() -> bool:
        machine = platform.machine()
        system = platform.system()

        if system == "Linux":
            return machine == "x86_64"

        # Note even on arm64 (e.g. aarch64, Apple Silicon M1) we use x86_64
        # binaries because of current ecosystem compatibility, but Rosetta will
        # make it work.
        elif system == "Darwin":
            return machine in {"x86_64", "arm64"}

        # Conda supports Windows, but we can't because several programs we need
        # are not available for Windows.
        else:
            return False

    yield ('operating system is supported',
            supported_os())

    yield from test_rosetta_enabled()

    yield ("runtime data dir doesn't have spaces",
            " " not in str(RUNTIME_ROOT))


def set_default_config() -> None:
    """
    No-op.
    """
    pass


def update() -> RunnerUpdateStatus:
    """
    Update all installed packages with Micromamba.
    """
    current_version = (package_meta(NEXTSTRAIN_BASE) or {}).get("version")

    # We accept a package match spec, which one to three space-separated parts.¹
    # If we got a spec, then we need to handle updates a bit differently.
    #
    # ¹ <https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html#package-match-specifications>
    #
    if " " in NEXTSTRAIN_BASE.strip():
        pkg = PackageSpec.parse(NEXTSTRAIN_BASE)
        print(colored("bold", f"Updating {pkg.name} from {current_version} to {pkg.version_spec}…"))
        update_spec = NEXTSTRAIN_BASE

    else:
        latest_version = (package_distribution(NEXTSTRAIN_CHANNEL, NEXTSTRAIN_BASE) or {}).get("version")

        if latest_version:
            if latest_version == current_version:
                print(f"Conda package {NEXTSTRAIN_BASE} {current_version} already at latest version")
                print()
                return True

            print(colored("bold", f"Updating Conda package {NEXTSTRAIN_BASE} from {current_version} to {latest_version}…"))

            update_spec = f"{NEXTSTRAIN_BASE} =={latest_version}"

        else:
            warn(f"Unable to find latest version of {NEXTSTRAIN_BASE} package; falling back to non-specific update")

            print(colored("bold", f"Updating Conda package {NEXTSTRAIN_BASE} from {current_version}…"))

            update_spec = NEXTSTRAIN_BASE

    print()
    print(f"Updating Conda packages in {PREFIX}…")
    print(f"  - {update_spec}")

    try:
        micromamba("update", update_spec)
    except InternalError as err:
        warn(err)
        traceback.print_exc()
        return False

    # Clean up unnecessary caches
    print("Cleaning up…")
    try:
        micromamba("clean", "--all", add_prefix = False)
    except InternalError as err:
        warn(err)
        warn(f"Continuing anyway.")

    return True


def versions() -> Iterable[str]:
    try:
        yield package_version(NEXTSTRAIN_BASE)
    except OSError:
        pass

    try:
        yield capture_output([str(PREFIX_BIN / "augur"), "--version"])[0]
    except (OSError, subprocess.CalledProcessError):
        pass

    try:
        yield "auspice " + capture_output([str(PREFIX_BIN / "auspice"), "--version"])[0]
    except (OSError, subprocess.CalledProcessError):
        pass


def package_version(spec: str) -> str:
    name = package_name(spec)
    meta = package_meta(spec)

    if not meta:
        return f"{name} unknown"

    version = meta.get("version", "unknown")
    build   = meta.get("build",   "unknown")
    channel = meta.get("channel", "unknown")

    anaconda_channel = re.search(r'^https://conda[.]anaconda[.]org/(?P<repo>.+?)/(?:linux|osx)-64$', channel)

    if anaconda_channel:
        channel = anaconda_channel["repo"]

    return f"{name} {version} ({build}, {channel})"


def package_meta(spec: str) -> Optional[dict]:
    name = package_name(spec)
    metafile = next((PREFIX / "conda-meta").glob(f"{name}-*.json"), None)

    if not metafile:
        return None

    return json.loads(metafile.read_bytes())


def package_distribution(channel: str, package: str, version: str = None, label: str = "main") -> Optional[dict]:
    # If *package* is a package spec, convert it just to a name.
    package = package_name(package)

    if version is None:
        version = latest_package_label_version(channel, package, label)
        if version is None:
            warn(f"Could not find latest version of package {package!r} with label {label!r}.",
                 "\nUsing 'latest' version instead, which will be the latest version of the package regardless of label.")
            version = "latest"

    response = requests.get(f"https://api.anaconda.org/release/{urlquote(channel)}/{urlquote(package)}/{urlquote(version)}")
    response.raise_for_status()

    dists = response.json().get("distributions", [])

    system = platform.system()
    machine = platform.machine()

    if (system, machine) == ("Linux", "x86_64"):
        subdir = "linux-64"
    elif (system, machine) in {("Darwin", "x86_64"), ("Darwin", "arm64")}:
        # Use the x86 arch even on arm (https://docs.nextstrain.org/en/latest/reference/faq.html#why-intel-miniconda-installer-on-apple-silicon)
        subdir = "osx-64"
    else:
        raise InternalError(f"Unsupported system/machine: {system}/{machine}")

    # Releases have other attributes related to system/machine, but they're
    # informational-only and subdir is what Conda *actually* uses to
    # differentiate distributions/files/etc.  Use it too so we have the same
    # view of reality.
    subdir_dists = (d for d in dists if d.get("attrs", {}).get("subdir") == subdir)
    dist = max(subdir_dists, default=None, key=lambda d: d.get("attrs", {}).get("build_number", 0))

    return dist


def package_name(spec: str) -> str:
    return PackageSpec.parse(spec).name


def latest_package_label_version(channel: str, package: str, label: str) -> Optional[str]:
    response = requests.get(f"https://api.anaconda.org/package/{urlquote(channel)}/{urlquote(package)}/files")
    response.raise_for_status()

    label_files = (file for file in response.json() if label in file.get("labels", []))
    # Default '0-dev' should be the lowest version according to PEP440
    # See https://peps.python.org/pep-0440/#summary-of-permitted-suffixes-and-relative-ordering
    latest_file: dict = max(label_files, default={}, key=lambda file: parse_version_lax(file.get('version', '0-dev')))
    return latest_file.get("version")


class PackageSpec(NamedTuple):
    name: str
    version_spec: Optional[str] = None
    build_id: Optional[str] = None

    @staticmethod
    def parse(spec):
        """
        Splits a `Conda package match spec`_ into a tuple of (name, version_spec, build_id).

        Returns a :cls:`PackageSpec`.

        .. _Conda package match spec: https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/pkg-specs.html#package-match-specifications
        """
        parts = spec.split(maxsplit = 2)

        try:
            return PackageSpec(parts[0], parts[1], parts[2])
        except IndexError:
            try:
                return PackageSpec(parts[0], parts[1], None)
            except IndexError:
                return PackageSpec(parts[0], None, None)

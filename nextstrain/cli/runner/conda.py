"""
Run commands with access to a fully-managed Conda environment.


Environment variables
=====================

.. warning::
    For development only.  You don't need to set this during normal operation.

.. envvar:: NEXTSTRAIN_CONDA_CHANNEL

    Conda channel name (or URL) to use for Nextstrain packages not otherwise
    available via Bioconda (e.g. ``nextstrain-base``).

    Defaults to ``nextstrain``.

.. envvar:: NEXTSTRAIN_CONDA_BASE_PACKAGE

    Conda meta-package name to use for the Nextstrain base runtime dependencies.

    Defaults to ``nextstrain-base``.

.. envvar:: NEXTSTRAIN_CONDA_MICROMAMBA_VERSION

    Version of Micromamba to use for setup and upgrade of the Conda runtime
    env.  Must be a version available from the `conda-forge channel
    <https://anaconda.org/conda-forge/micromamba/>`__, or the special string
    ``latest``.

    Defaults to ``0.27.0``.
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
from typing import Iterable
from urllib.parse import urljoin, quote as urlquote
from ..errors import InternalError
from ..paths import RUNTIMES
from ..types import RunnerSetupStatus, RunnerTestResults, RunnerUpdateStatus
from ..util import capture_output, exec_or_return, warn


RUNTIME_ROOT = RUNTIMES / "conda/"

PREFIX     = RUNTIME_ROOT / "env/"
PREFIX_BIN = PREFIX / "bin"

MICROMAMBA_ROOT = RUNTIME_ROOT / "micromamba/"
MICROMAMBA      = MICROMAMBA_ROOT / "bin/micromamba"

# If you update the version pin below, please update the docstring above too.
MICROMAMBA_VERSION = os.environ.get("NEXTSTRAIN_CONDA_MICROMAMBA_VERSION") \
                  or "0.27.0"

NEXTSTRAIN_CHANNEL = os.environ.get("NEXTSTRAIN_CONDA_CHANNEL") \
                  or "nextstrain"

NEXTSTRAIN_BASE = os.environ.get("NEXTSTRAIN_CONDA_BASE_PACKAGE") \
               or "nextstrain-base"


def register_arguments(parser) -> None:
    """
    No-op.  No arguments necessary.
    """
    pass


def run(opts, argv, working_volume = None, extra_env = {}, cpus: int = None, memory: int = None) -> int:
    if working_volume:
        os.chdir(str(working_volume.src))

    # XXX TODO: In the future we might want to set rlimits based on cpus and
    # memory, at least on POSIX systems.
    #   -trs, 21 May 2020 (copied from ./native.py on 30 Aug 2022)

    extra_env.update({
        "PATH": path_with_prefix(),
    })

    return exec_or_return(argv, extra_env)


def path_with_prefix() -> str:
    """
    Constructs a ``PATH`` with our runtime prefix.

    The returned ``PATH`` consists of the:

      1. Runtime prefix
      2. :py:attr:`os.defpath`

    which provides some, but not total, isolation from the rest of the system.
    """
    return os.pathsep.join(map(str, [
        # Programs installed by this runtime.
        PREFIX_BIN,

        # Python's idea of a default path for the system, which currently under
        # CPython is either "/bin:/usr/bin" on POSIX systems or ".;C:\\bin" on
        # Windows.  This will ensure basic system commands like `ls` are
        # available, although it will also "leak" any user-installed programs
        # there.
        os.defpath,
    ]))


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
    response = requests.get(f"https://api.anaconda.org/release/conda-forge/micromamba/{urlquote(MICROMAMBA_VERSION)}")
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
        warn(f"Unsupported system/machine: {system}/{machine}")
        return False

    # Releases have other attributes related to system/machine, but they're
    # informational-only and subdir is what Conda *actually* uses to
    # differentiate distributions/files/etc.  Use it too so we have the same
    # view of reality.
    dist = next((d for d in dists if d.get("attrs", {}).get("subdir") == subdir), None)

    assert dist, f"unable to find micromamba dist with subdir == {subdir!r}"

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

    # Conda packages to install.
    #
    # HEY YOU: If you add/remove packages here, make sure to account for how
    # update() should make the same changes to existing envs.
    #   -trs, 1 Sept 2022
    packages = (
        NEXTSTRAIN_BASE,
    )

    # Create environment
    print(f"Installing Conda packages into {PREFIX}…")
    for pkg in packages:
        print(f"  - {pkg}")

    if not dry_run:
        try:
            micromamba("create", *packages)
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

    def which_finds_our(cmd) -> bool:
        # which() checks executability and also handles PATHEXT, e.g. the
        # ".exe" extension on Windows, which is why we don't just naively test
        # for existence ourselves.  File extensions are also why we don't test
        # equality below instead check containment in PREFIX_BIN.
        found = shutil.which(cmd, path = path_with_prefix())

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
            capture_output(argv, extra_env = {"PATH": path_with_prefix()})
            return True
        except (OSError, subprocess.CalledProcessError):
            return False


    return [
        ('operating system is supported',
            supported_os()),

        ("runtime data dir doesn't have spaces",
            " " not in str(RUNTIME_ROOT)),

        ('snakemake is installed and runnable',
            which_finds_our("snakemake") and runnable("snakemake", "--version")),

        ('augur is installed and runnable',
            which_finds_our("augur") and runnable("augur", "--version")),

        ('auspice is installed and runnable',
            which_finds_our("auspice") and runnable("auspice", "--version")),
    ]


def set_default_config() -> None:
    """
    No-op.
    """
    pass


def update() -> RunnerUpdateStatus:
    """
    Update all installed packages with Micromamba.
    """
    print("Updating Conda packages…")
    try:
        micromamba("update", NEXTSTRAIN_BASE)
    except InternalError as err:
        warn(err)
        traceback.print_exc()
        return False

    return True


def versions() -> Iterable[str]:
    try:
        yield package_version("nextstrain-base")
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


def package_version(name: str) -> str:
    metafile = next((PREFIX / "conda-meta").glob(f"{name}-*.json"), None)

    if not metafile:
        return f"{name} unknown"

    meta = json.loads(metafile.read_bytes())

    version = meta.get("version", "unknown")
    build   = meta.get("build",   "unknown")
    channel = meta.get("channel", "unknown")

    anaconda_channel = re.search(r'^https://conda[.]anaconda[.]org/(?P<repo>.+?)/(?:linux|osx)-64$', channel)

    if anaconda_channel:
        channel = anaconda_channel["repo"]

    return f"{name} {version} ({build}, {channel})"

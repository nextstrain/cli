"""
Run commands with access to a fully-managed Conda environment.
"""

import os
import platform
import requests
import shutil
import subprocess
import tarfile
import traceback
from pathlib import Path, PurePosixPath
from typing import Iterable, Tuple
from urllib.parse import urljoin
from ..paths import RUNTIMES
from ..types import RunnerSetupStatus, RunnerTestResults, RunnerUpdateStatus
from ..util import capture_output, exec_or_return, warn


RUNTIME_ROOT = RUNTIMES / "managed-conda/"

PREFIX     = RUNTIME_ROOT / "env/"
PREFIX_BIN = PREFIX / "bin"

MICROMAMBA_ROOT = RUNTIME_ROOT / "micromamba/"
MICROMAMBA      = MICROMAMBA_ROOT / "bin/micromamba"


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

    # Query for latest Micromamba release
    dists = (
        requests.get("https://api.anaconda.org/release/conda-forge/micromamba/latest")
            .json()
            .get("distributions", []))

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

    # Conda packages to install, based on our unmanaged "native" install docs.
    #
    # Includes nextstrain-cli even though that's us and we're already installed
    # and running because our own executable may not be on PATH in the runtime
    # environment.
    #
    # Adds bash so that a newer version is guaranteed to be available on
    # systems with an older bash.  This is similar to how our Docker runtime
    # image includes its own bash too.
    #
    # HEY YOU: If you add/remove packages here, make sure to account for how
    # update() should make the same changes to existing envs.
    #   -trs, 1 Sept 2022
    packages = (
        "augur",
        "auspice",
        "nextalign",
        "nextclade",
        "nextstrain-cli",

        "bash",
        "epiweeks",
        "git",
        "pangolearn",
        "pangolin",
        "snakemake",
    )

    # Create environment
    create = micromamba(
        "create",

        # Path-based env
        "--prefix", PREFIX,

        # BioConda config per <https://bioconda.github.io/#usage>
        "--override-channels",
        "--strict-channel-priority",
        "--channel", "conda-forge",
        "--channel", "bioconda",
        "--channel", "defaults",

        *packages,
    )

    print(f"Installing Conda packages into {PREFIX}…")
    for pkg in packages:
        print(f"  - {pkg}")

    if not dry_run:
        try:
            subprocess.run(create, check = True)
        except (OSError, subprocess.CalledProcessError):
            warn(f"Error running {create!r}")
            traceback.print_exc()
            return False

    # Clean up unnecessary caches
    clean = micromamba("clean", "--all")

    print("Cleaning up…")

    if not dry_run:
        try:
            subprocess.run(clean, check = True)
        except (OSError, subprocess.CalledProcessError) as error:
            warn(f"Error cleaning up with {clean!r}: {error}")
            warn(f"Continuing anyway.")

    return True


def micromamba(*args) -> Tuple[str, ...]:
    """
    Runs our installed Micromamba with appropriate global options.

    For convenience, all arguments are converted to strings, making the return
    value suitable for passing directly to :py:func:`subprocess.run`.
    """
    return tuple(map(str, (
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

    return [
        ('operating system is supported',
            supported_os()),

        ("runtime data dir doesn't have spaces",
            " " not in str(RUNTIME_ROOT)),

        ('snakemake is installed',
            which_finds_our("snakemake")),

        ('augur is installed',
            which_finds_our("augur")),

        ('auspice is installed',
            which_finds_our("auspice")),
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
    update = micromamba("update", "--all", "--prefix", PREFIX)

    print("Updating Conda packages…")
    try:
        subprocess.run(update, check = True)
    except (OSError, subprocess.CalledProcessError):
        warn(f"Error running {update!r}")
        traceback.print_exc()
        return False

    return True


def versions() -> Iterable[str]:
    try:
        yield capture_output([str(PREFIX_BIN / "augur"), "--version"])[0]
    except (OSError, subprocess.CalledProcessError):
        pass

    try:
        yield "auspice " + capture_output([str(PREFIX_BIN / "auspice"), "--version"])[0]
    except (OSError, subprocess.CalledProcessError):
        pass

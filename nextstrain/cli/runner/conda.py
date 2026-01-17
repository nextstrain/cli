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

.. envvar:: NEXTSTRAIN_CONDA_CHANNEL_ALIAS

    The base URL to prepend to channel names.  Equivalent to the |channel_alias
    Conda config setting|_.

    Useful if you want to use a Conda package mirror that's not the default
    (i.e. not Anaconda's).

    Defaults to the Conda ecosystem's default of
    `<https://conda.anaconda.org/>`__.

.. |channel_alias Conda config setting| replace:: ``channel_alias`` Conda config setting
.. _channel_alias Conda config setting: https://docs.conda.io/projects/conda/en/latest/user-guide/configuration/settings.html#set-ch-alias


.. warning::
    The remaining variables are for development only.  You don't need to set
    these during normal operation.

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

.. envvar:: NEXTSTRAIN_CONDA_MICROMAMBA_URL

    URL of a Micromamba release tarball (e.g. Conda package) to use for setup
    and updates.

    May be a full URL or a relative URL to be joined with
    :envvar:`NEXTSTRAIN_CONDA_CHANNEL_ALIAS`.  Any occurrence of ``{subdir}``
    will be replaced with the current platform's Conda subdir value.

    Replaces the previously-supported development environment variable
    ``NEXTSTRAIN_CONDA_MICROMAMBA_VERSION``.

    Defaults to ``conda-forge/{subdir}/micromamba-1.5.8-0.tar.bz2``.

.. envvar:: NEXTSTRAIN_CONDA_OVERRIDE_SUBDIR

    Conda subdir to use for both Micromamba and the runtime environment.

    If set, overrides the default behaviour of detecting the best subdir that's
    usable for the platform.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import traceback
from pathlib import Path, PurePosixPath
from tempfile import TemporaryFile
from typing import IO, Iterable, List, NamedTuple, Optional, cast
from urllib.parse import urljoin
from .. import config
from .. import requests
from ..errors import InternalError, UserError
from ..paths import RUNTIMES
from ..types import Env, RunnerModule, SetupStatus, SetupTestResults, UpdateStatus
from ..util import capture_output, colored, exec_or_return, parse_version_lax, runner_name, setup_tests_ok, test_rosetta_enabled, uniq, warn


RUNTIME_ROOT = RUNTIMES / "conda/"

PREFIX     = RUNTIME_ROOT / "env/"
PREFIX_BIN = PREFIX / "bin"

MICROMAMBA_ROOT = RUNTIME_ROOT / "micromamba/"
MICROMAMBA      = MICROMAMBA_ROOT / "bin/micromamba"

# If you update the version pin below, please update the docstring above too.
MICROMAMBA_URL = os.environ.get("NEXTSTRAIN_CONDA_MICROMAMBA_URL") \
              or "conda-forge/{subdir}/micromamba-1.5.8-0.tar.bz2"

CHANNEL_ALIAS = os.environ.get("NEXTSTRAIN_CONDA_CHANNEL_ALIAS") \
             or "https://conda.anaconda.org"

NEXTSTRAIN_CHANNEL = os.environ.get("NEXTSTRAIN_CONDA_CHANNEL") \
                  or "nextstrain"

NEXTSTRAIN_BASE = os.environ.get("NEXTSTRAIN_CONDA_BASE_PACKAGE") \
               or "nextstrain-base"

OVERRIDE_SUBDIR = os.environ.get("NEXTSTRAIN_CONDA_OVERRIDE_SUBDIR")

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


def setup(dry_run: bool = False, force: bool = False) -> SetupStatus:
    return _setup(dry_run, force)


def _setup(dry_run: bool = False, force: bool = False, install_dist: 'PackageDistribution' = None) -> SetupStatus:
    if not setup_micromamba(dry_run, force):
        return False

    if not setup_prefix(dry_run, force, install_dist):
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

    try:
        subdir = OVERRIDE_SUBDIR or platform_subdir()
    except InternalError as err:
        warn(err)
        return False

    url = urljoin(CHANNEL_ALIAS, MICROMAMBA_URL.replace('{subdir}', subdir))

    print(f"Requesting Micromamba from {url}…")

    if not dry_run:
        response = requests.get(url, stream = True)
        response.raise_for_status()
        content_type = response.headers["Content-Type"]

        try:
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

        except tarfile.TarError as err:
            raise UserError(f"""
                Failed to extract {url} (Content-Type: {content_type}) as tar archive: {err}
                """)
    else:
        print(f"Downloading and extracting Micromamba to {MICROMAMBA_ROOT}…")

    return True


def setup_prefix(dry_run: bool = False, force: bool = False, install_dist: 'PackageDistribution' = None) -> bool:
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

    if not install_dist:
        if OVERRIDE_SUBDIR:
            subdirs = [OVERRIDE_SUBDIR]
        else:
            subdirs = [platform_subdir(), *alternate_platform_subdirs()]

        for subdir in subdirs:
            if install_dist := package_distribution(NEXTSTRAIN_CHANNEL, NEXTSTRAIN_BASE, subdir):
                break
        else:
            raise UserError(f"Unable to find latest version of {NEXTSTRAIN_BASE} package in {NEXTSTRAIN_CHANNEL}")

    install_spec = f"{install_dist.name} =={install_dist.version}"

    # Create environment
    print(f"Installing Conda packages into {PREFIX}…")
    print(f"  - {install_spec} ({install_dist.subdir})")

    if not dry_run:
        try:
            micromamba("create", install_spec, "--platform", install_dist.subdir)
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


def micromamba(*args, stdout: IO[bytes] = None, add_prefix: bool = True) -> None:
    """
    Runs our installed Micromamba with appropriate global options and options
    for prefix and channel selection.

    Invokes :py:func:`subprocess.run` and checks the exit status.  Raises a
    :py:exc:`InternalError` on failure, chained from the original
    :py:exc:`OSError` or :py:exc:`subprocess.CalledProcessError`.

    For convenience, all arguments are converted to strings before being passed
    to :py:func:`subprocess.run`.

    Set the keyword-only argument *stdout* to a binary file-like object (with a
    file descriptor) to redirect the process's stdout.

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
            "--channel", urljoin(CHANNEL_ALIAS, NEXTSTRAIN_CHANNEL),
            "--channel", urljoin(CHANNEL_ALIAS, "conda-forge"),
            "--channel", urljoin(CHANNEL_ALIAS, "bioconda"),

            # Don't automatically pin Python so nextstrain-base deps can change
            # it on upgrade.
            "--no-py-pin",

            # Allow uninstalls and downgrades of existing installed packages so
            # nextstrain-base deps can change on upgrade.  Uninstalls are
            # currently allowed by default (unlike downgrades), but make it
            # explicit here.
            "--allow-uninstall",
            "--allow-downgrade",

            # Honor same method of CA certificate overriding as requests,
            # except without support for cert directories (only files).
            *(["--cacert-path", requests.CA_BUNDLE]
                if not Path(requests.CA_BUNDLE).is_dir() else []),
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
        subprocess.run(argv, env = env, stdout = stdout, check = True)
    except (OSError, subprocess.CalledProcessError) as err:
        raise InternalError(f"Error running {argv!r}") from err


def test_setup() -> SetupTestResults:
    def which_finds_our(cmd) -> bool:
        # which() checks executability and also handles PATHEXT, e.g. the
        # ".exe" extension on Windows, which is why we don't just naively test
        # for existence ourselves.  File extensions are also why we don't test
        # equality below instead check containment in PREFIX_BIN.
        found = shutil.which(cmd, path = PATH)

        if not found:
            return False

        return Path(found).is_relative_to(PREFIX_BIN)


    def runnable(*argv) -> bool:
        try:
            capture_output(argv, extra_env = EXEC_ENV)
            return True
        except (OSError, subprocess.CalledProcessError):
            return False


    support = list(test_support())

    yield from support

    if not setup_tests_ok(support):
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


def test_support() -> SetupTestResults:
    def supported_os() -> bool:
        machine = platform.machine()
        system = platform.system()

        if system == "Linux":
            return machine == "x86_64"

        elif system == "Darwin":
            return machine in {"x86_64", "arm64"}

        # Conda supports Windows, but we can't because several programs we need
        # are not available for Windows.
        else:
            return False

    yield ('operating system is supported',
            supported_os())

    yield ("runtime data dir doesn't have spaces",
            " " not in str(RUNTIME_ROOT))


def set_default_config() -> None:
    """
    Sets ``core.runner`` to this runner's name (``conda``).
    """
    config.set("core", "runner", runner_name(cast(RunnerModule, sys.modules[__name__])))


def update() -> UpdateStatus:
    """
    Update all installed packages with Micromamba.
    """
    # In the comparisons and logic below, we handle selecting the version to
    # update to but still let Micromamba select the specific package _build_ to
    # use.  While our package creation automation currently doesn't support
    # multiple builds of a version, it's worth noting that 1) Conda's data
    # model allows for it, and 2) we may start producing multiple builds in the
    # future (e.g. for varying x86_64-microarch-level dependencies¹ or other
    # platform compatibility reasons).  If we do, the code below should still
    # work fine.  However, if we start making "fixup" builds of existing
    # versions (e.g.  build 1 of version X after build 0 of version X), the "do
    # we need to update?" logic below would not deal with them properly.
    #   -trs, 9 April 2025 & 13 May 2025
    #
    # ¹ <https://github.com/nextstrain/conda-base/issues/105>

    nextstrain_base = PackageSpec.parse(NEXTSTRAIN_BASE)

    current_meta = package_meta(NEXTSTRAIN_BASE) or {}
    current_version = current_meta.get("version")
    current_subdir = current_meta.get("subdir") or OVERRIDE_SUBDIR or platform_subdir()

    assert current_meta.get("name") in {nextstrain_base.name, None}

    # Prefer the platform subdir if possible (e.g. to migrate from osx-64 →
    # osx-arm64).  Otherwise, use the prefix's current subdir or alternate
    # platform subdirs (e.g. to allow "downgrade" from osx-arm64 → osx-64).
    if OVERRIDE_SUBDIR:
        subdirs = [OVERRIDE_SUBDIR]
    else:
        subdirs = uniq([platform_subdir(), current_subdir, *alternate_platform_subdirs()])

    for subdir in subdirs:
        if latest_dist := package_distribution(NEXTSTRAIN_CHANNEL, NEXTSTRAIN_BASE, subdir):
            assert latest_dist.name == nextstrain_base.name
            break
    else:
        raise UserError(f"Unable to find latest version of {NEXTSTRAIN_BASE} package in {NEXTSTRAIN_CHANNEL}")

    latest_version = latest_dist.version
    latest_subdir = latest_dist.subdir

    if latest_version == current_version:
        print(f"Conda package {nextstrain_base.name} {current_version} already at latest version")
    else:
        print(colored("bold", f"Updating Conda package {nextstrain_base.name} from {current_version} to {latest_version}…"))

    # Do we need to force a new setup?
    if current_subdir != latest_subdir:
        print(f"Updating platform from {current_subdir} → {latest_subdir} by setting up from scratch again…")
        return _setup(install_dist = latest_dist, dry_run = False, force = True)

    # Anything to do?
    if latest_version == current_version:
        return True

    update_spec = f"{latest_dist.name} =={latest_version}"

    print()
    print(f"Updating Conda packages in {PREFIX}…")
    print(f"  - {update_spec} ({latest_dist.subdir})")

    try:
        micromamba("update", update_spec, "--platform", latest_dist.subdir)
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
    channel = meta.get("channel", "unknown") # full URL; includes subdir

    return f"{name} {version} ({build}, {channel})"


def package_meta(spec: str) -> Optional[dict]:
    name = package_name(spec)
    metafile = next((PREFIX / "conda-meta").glob(f"{name}-*.json"), None)

    if not metafile:
        return None

    return json.loads(metafile.read_bytes())


def package_distribution(channel: str, spec: str, subdir: str) -> Optional['PackageDistribution']:
    with TemporaryFile() as tmp:
        micromamba(
            "repoquery", "search", spec,

            # Channel (repo) to search
            "--override-channels",
            "--strict-channel-priority",
            "--channel", urljoin(CHANNEL_ALIAS, channel),
            "--platform", subdir,

            # Always check that we have latest package index
            "--repodata-ttl", 0,

            # Emit JSON so we can process it
            "--json",

            # Honor same method of CA certificate overriding as requests,
            # except without support for cert directories (only files).
            *(["--cacert-path", requests.CA_BUNDLE]
                if not Path(requests.CA_BUNDLE).is_dir() else []),

            add_prefix = False,
            stdout = tmp)

        tmp.seek(0)

        result = json.load(tmp).get("result", {})

    assert (status := result.get("status")) == "OK", \
        f"repoquery {status=}, not OK"

    dists = result.get("pkgs", [])

    # Default '0-dev' should be the lowest version according to PEP440.¹
    #
    # We're intentionally ignoring build number as we let Micromamba sort out
    # the best build variant for a given version of our nextstrain-base
    # package.  We currently do not produce multiple builds per version, but we
    # may in the future.  See also the comment at the top of update().
    #
    # ¹ <https://peps.python.org/pep-0440/#summary-of-permitted-suffixes-and-relative-ordering>
    dist = max(dists, default = None, key = lambda d: parse_version_lax(d.get("version", "0-dev")))

    if not dist:
        return None

    return PackageDistribution(dist["name"], dist["version"], dist["subdir"])


class PackageDistribution(NamedTuple):
    name: str
    version: str
    subdir: str


def package_name(spec: str) -> str:
    return PackageSpec.parse(spec).name


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


def platform_subdir() -> str:
    """
    Conda subdir to use for the :mod:`platform` on which we're running.

    One of ``linux-64``, ``osx-64``, or ``osx-arm64``.

    Raises an :exc:`InternalError` if the platform is currently unsupported.
    """
    system = platform.system()
    machine = platform.machine()

    if (system, machine) == ("Linux", "x86_64"):
        subdir = "linux-64"
    elif (system, machine) == ("Darwin", "x86_64"):
        subdir = "osx-64"
    elif (system, machine) == ("Darwin", "arm64"):
        subdir = "osx-arm64"
    else:
        raise InternalError(f"Unsupported system/machine: {system}/{machine}")

    return subdir


def alternate_platform_subdirs() -> List[str]:
    """
    Alternative Conda subdirs that this :mod:`platform` can use.
    """
    system = platform.system()
    machine = platform.machine()

    if (system, machine) == ("Darwin", "arm64"):
        if setup_tests_ok(test_rosetta_enabled()):
            return ["osx-64"]

    return []

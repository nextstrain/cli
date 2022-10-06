"""
Run commands in the ambient environment, outside of any container image.
"""

import os
import shutil
from subprocess import CalledProcessError
from typing import Iterable
from ..types import RunnerSetupStatus, RunnerTestResults, RunnerUpdateStatus
from ..util import capture_output, exec_or_return


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
    #   -trs, 21 May 2020

    return exec_or_return(argv, extra_env)


def setup(dry_run: bool = False, force: bool = False) -> RunnerSetupStatus:
    """
    Not supported.
    """
    return None


def test_setup() -> RunnerTestResults:
    def runnable(*argv) -> bool:
        try:
            capture_output(argv)
            return True
        except (OSError, CalledProcessError):
            return False


    return [
        ('snakemake is installed and runnable',
            shutil.which("snakemake") is not None and runnable("snakemake", "--version")),

        ('augur is installed and runnable',
            shutil.which("augur") is not None and runnable("augur", "--version")),

        ('auspice is installed and runnable',
            shutil.which("auspice") is not None and runnable("auspice", "--version")),
    ]


def set_default_config() -> None:
    """
    No-op.
    """
    pass


def update() -> RunnerUpdateStatus:
    """
    Not supported.  Updating the ambient environment isn't reasonably possible.
    """
    return None


def versions() -> Iterable[str]:
    try:
        yield capture_output(["augur", "--version"])[0]
    except (OSError, CalledProcessError):
        pass

    try:
        yield "auspice " + capture_output(["auspice", "--version"])[0]
    except (OSError, CalledProcessError):
        pass

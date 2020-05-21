"""
Run commands on the native host, outside of any container image.
"""

import os
import shutil
from subprocess import CalledProcessError
from typing import Iterable
from ..types import RunnerTestResults
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


def test_setup() -> RunnerTestResults:
    return [
        ('snakemake is installed',
            shutil.which("snakemake") is not None),

        ('augur is installed',
            shutil.which("augur") is not None),

        ('auspice is installed',
            shutil.which("auspice") is not None),
    ]


def update() -> bool:
    """
    No-op.  Updating the native environment isn't reasonably possible.
    """
    return True


def versions() -> Iterable[str]:
    try:
        yield capture_output(["augur", "--version"])[0]
    except (OSError, CalledProcessError):
        pass

    try:
        yield "auspice " + capture_output(["auspice", "--version"])[0]
    except (OSError, CalledProcessError):
        pass

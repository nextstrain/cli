"""
Run commands in the ambient environment, outside of any container image or managed environment.

The "ambient" runtime allows you to use the Nextstrain CLI with your own ambient
setup, for when you cannot or do not want to have Nextstrain CLI manage its own
runtime.

.. versionadded:: 1.5.0
.. versionchanged:: 5.0.0
    Renamed from "native" to "ambient".


.. _ambient-setup:

Setup
=====

You will need to make sure all of the Nextstrain software dependencies
are available locally or "ambiently" on your computer.

A common way to do this is by manually using `Conda
<https://docs.conda.io/en/latest/miniconda.html>`__ to manage your own
environment that includes the required software, however you're responsible for
making sure the correct software is installed and kept up-to-date. Our
:doc:`general Nextstrain installation page <docs:install>` describes more
comprehensively how to do this.

It is also possible to install the required Nextstrain software `Augur
<https://github.com/nextstrain/augur>`__ and `Auspice
<https://github.com/nextstrain/auspice>`__ and their dependencies manually,
although this is not recommended.

Once you've installed dependencies, proceed with ``nextstrain setup ambient``.
"""

import os
import shutil
import sys
from subprocess import CalledProcessError
from typing import Iterable, cast
from .. import config
from ..types import Env, RunnerModule, SetupStatus, SetupTestResults, UpdateStatus
from ..util import capture_output, exec_or_return, runner_name


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
    #   -trs, 21 May 2020

    return exec_or_return(argv, extra_env)


def setup(dry_run: bool = False, force: bool = False) -> SetupStatus:
    """
    Not supported.
    """
    return None


def test_setup() -> SetupTestResults:
    def runnable(*argv) -> bool:
        try:
            capture_output(argv)
            return True
        except (OSError, CalledProcessError):
            return False


    yield ('snakemake is installed and runnable',
            shutil.which("snakemake") is not None and runnable("snakemake", "--version"))

    yield ('augur is installed and runnable',
            shutil.which("augur") is not None and runnable("augur", "--version"))

    yield ('auspice is installed and runnable',
            shutil.which("auspice") is not None and runnable("auspice", "--version"))


def set_default_config() -> None:
    """
    Sets ``core.runner`` to this runner's name (``ambient``).
    """
    config.set("core", "runner", runner_name(cast(RunnerModule, sys.modules[__name__])))


def update() -> UpdateStatus:
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

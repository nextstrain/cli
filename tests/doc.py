import os
import pytest
from pathlib import Path
from subprocess import run

topdir = Path(__file__).resolve().parent.parent

@pytest.mark.skipif(os.name != "posix", reason = "devel/generate-command-doc requires a POSIX platform")
def pytest_generated_command_doc():
    # Check the exit status ourselves for nicer test output on failure
    result = run([topdir / "devel/generate-command-doc", "--check", "--diff"])
    assert result.returncode == 0, f"{result.args!r} exited with errors"

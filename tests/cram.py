import os
import pytest
from pathlib import Path
from subprocess import run

testsdir = Path(__file__).resolve().parent
topdir = testsdir.parent

@pytest.mark.skipif(os.name != "posix", reason = "cram requires a POSIX platform")
@pytest.mark.parametrize("testfile", testsdir.glob("*.cram"), ids = str)
def pytest_cram(testfile):
    # Check the exit status ourselves for nicer test output on failure
    result = run(["cram", testfile], cwd = topdir)
    assert result.returncode == 0, "cram exited with errors"

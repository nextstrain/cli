import os
import pytest
from pathlib import Path
from subprocess import run

topdir = Path(__file__).resolve().parent.parent

generator_progs = [
    "devel/generate-command-doc",
    "devel/generate-changes-doc",
]

@pytest.mark.skipif(os.name != "posix", reason = "doc generation requires a POSIX platform")
@pytest.mark.parametrize("prog", generator_progs, ids = str)
def pytest_generated_doc(prog):
    # Check the exit status ourselves for nicer test output on failure
    result = run([topdir / prog, "--check", "--diff"])
    assert result.returncode == 0, f"{result.args!r} exited with errors"

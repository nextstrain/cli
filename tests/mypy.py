from pathlib import Path
from subprocess import run

topdir = Path(__file__).resolve().parent.parent

def pytest_mypy():
    # Check the exit status ourselves for nicer test output on failure
    result = run(["mypy", "-p", "nextstrain.cli"], cwd = topdir)
    assert result.returncode == 0, "mypy exited with errors"

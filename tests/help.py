import pytest
import os
from nextstrain.cli import make_parser
from nextstrain.cli.argparse import walk_commands
from subprocess import run



commands = list(walk_commands(("nextstrain",), make_parser()))


@pytest.mark.parametrize("command", commands, ids = lambda command: " ".join(command))
def pytest_help(command):
    # Check the exit status ourselves for nicer test output on failure
    argv = (*command, "--help")

    result = run(argv)
    assert result.returncode == 0, f"{argv} exited with error"

    result = run(argv, env = {**os.environ, "NEXTSTRAIN_RST_STRICT": "yes"})
    assert result.returncode == 0, f"{argv} exited with error with strict rST conversion"

import pytest
import os
from nextstrain.cli import make_parser
from nextstrain.cli.argparse import walk_commands
from subprocess import run


def generate_commands():
    for command, parser in walk_commands(make_parser()):
        has_extended_help = any(
            any(opt == "--help-all" for opt in action.option_strings)
                for action in parser._actions)

        yield (*command, "--help-all" if has_extended_help else "--help")


commands = list(generate_commands())


@pytest.mark.parametrize("command", commands, ids = lambda command: " ".join(command))
def pytest_help(command):
    # Check the exit status ourselves for nicer test output on failure
    result = run(command)
    assert result.returncode == 0, f"{command} exited with error"

    result = run(command, env = {**os.environ, "NEXTSTRAIN_RST_STRICT": "yes"})
    assert result.returncode == 0, f"{command} exited with error with strict rST conversion"

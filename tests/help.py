import pytest
import argparse
import os
from itertools import chain
from nextstrain.cli import make_parser
from subprocess import run


def walk_commands(command, parser):
    yield command

    subparsers = chain.from_iterable(
        action.choices.items()
            for action in parser._actions
             if isinstance(action, argparse._SubParsersAction))

    for subname, subparser in subparsers:
        yield from walk_commands([*command, subname], subparser)


commands = list(walk_commands(("nextstrain",), make_parser()))


@pytest.mark.parametrize("command", commands, ids = lambda command: " ".join(command))
def pytest_help(command):
    # Check the exit status ourselves for nicer test output on failure
    argv = (*command, "--help")

    result = run(argv)
    assert result.returncode == 0, f"{argv} exited with error"

    result = run(argv, env = {**os.environ, "NEXTSTRAIN_RST_STRICT": "yes"})
    assert result.returncode == 0, f"{argv} exited with error with strict rST conversion"

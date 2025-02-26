"""
Start a new shell inside a Nextstrain runtime to run ad-hoc
commands and perform debugging.
"""

from pathlib import Path
from typing import Tuple
from .. import resources
from .. import runner
from ..argparse import add_extended_help_flags
from ..paths import SHELL_HISTORY
from ..runner import docker, conda, singularity
from ..util import colored, remove_prefix, runner_name
from ..volume import NamedVolume
from .build import assert_overlay_volumes_support, pathogen_volumes


def register_parser(subparser):
    """
    %(prog)s [options] <directory> [...]
    %(prog)s --help
    """

    parser = subparser.add_parser("shell", help = "Start a new shell in a runtime", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        type    = Path)

    # Register runner flags and arguments; excludes ambient and AWS Batch
    # runners since those don't make any sense here.
    runner.register_runners(
        parser,
        exec    = ["bash", ...],
        runners = [docker, conda, singularity])

    return parser


def run(opts):
    assert_overlay_volumes_support(opts)

    # Interpret the given directory
    build_volume, working_volume = pathogen_volumes(opts.directory)

    opts.volumes.append(build_volume) # for Docker and Singularity

    print(colored("bold", f"Entering the Nextstrain runtime ({runner_name(opts.__runner__)})"))
    print()

    if opts.volumes and opts.__runner__ in {docker, singularity}:
        print(colored("bold", "Mapped volumes:"))

        # This is more tightly coupled to the Docker/Singularity runners than
        # I'd like (i.e.  assuming /nextstrain/…), but the number of runtimes
        # will always be small so some special-casing seems ok.
        #   -trs, 5 Jan 2023 (updated from 25 Sept 2018)
        for volume in opts.volumes:
            print("  %s is from %s" % (docker.mount_point(volume), volume.src.resolve(strict = True)))

        print()

    print(colored("bold", 'Run the command "exit" to leave the runtime.'))
    print()

    with resources.as_file("bashrc") as bashrc:
        # Ensure the history file exists to pass checks the Docker/Singularity
        # runners perform for mounted volumes.  This also makes sure that the
        # file is writable by the Conda runtime too by ensuring the parent
        # directory exists.
        #
        # Don't use strict=True because it's ok if it doesn't exist yet!
        history_file = SHELL_HISTORY.resolve()
        history_file.parent.mkdir(parents = True, exist_ok = True)

        try:
            # Don't use exist_ok=True so we don't touch the mtime unnecessarily
            history_file.touch()
        except FileExistsError:
            pass

        if opts.__runner__ is conda:
            opts.default_exec_args = [
                *opts.default_exec_args,
                "--rcfile", str(bashrc),
            ]

        elif opts.__runner__ in {docker, singularity}:
            opts.volumes.append(NamedVolume("bashrc", bashrc, dir = False, writable = False))

            history_volume = NamedVolume("bash_history", history_file, dir = False)
            history_file = docker.mount_point(history_volume)
            opts.volumes.append(history_volume)

        extra_env = {
            "NEXTSTRAIN_PS1": ps1(),
            "NEXTSTRAIN_HISTFILE": str(history_file),
        }

        return runner.run(opts, working_volume = working_volume, extra_env = extra_env)


def ps1() -> str:
    # ESC[ 38;2;⟨r⟩;⟨g⟩;⟨b⟩ m — Select RGB foreground color
    # ESC[ 48;2;⟨r⟩;⟨g⟩;⟨b⟩ m — Select RGB background color
    def fg(color: str) -> str: return r'\[\e[38;2;{};{};{}m\]'.format(*rgb(color))
    def bg(color: str) -> str: return r'\[\e[48;2;{};{};{}m\]'.format(*rgb(color))

    def rgb(color: str) -> Tuple[int, int, int]:
        color = remove_prefix("#", color)
        r,g,b = (int(c, 16) for c in (color[0:2], color[2:4], color[4:6]))
        return r,g,b

    wordmark = (
        (' ', '#4377cd'),
        ('N', '#4377cd'),
        ('e', '#5097ba'),
        ('x', '#63ac9a'),
        ('t', '#7cb879'),
        ('s', '#9abe5c'),
        ('t', '#b9bc4a'),
        ('r', '#d4b13f'),
        ('a', '#e49938'),
        ('i', '#e67030'),
        ('n', '#de3c26'),
        (' ', '#de3c26'))

    # Bold, bright white text (fg)…
    PS1 = r'\[\e[1;97m\]'

    # …on a colored background
    for letter, color in wordmark:
        PS1 += bg(color) + letter

    # Add working dir and traditional prompt char (in magenta)
    PS1 += r'\[\e[0m\] \w' + fg('#ff00ff') + r' \$ '

    # Reset
    PS1 += r'\[\e[0m\]'

    return PS1

"""
Start a new shell inside the Nextstrain build environment to run ad-hoc
commands and perform debugging.
"""

from typing import Tuple
from .. import resources
from .. import runner
from ..argparse import add_extended_help_flags
from ..errors import UserError
from ..paths import SHELL_HISTORY
from ..runner import docker, conda
from ..util import colored, remove_prefix, runner_name, warn
from ..volume import store_volume, NamedVolume


def register_parser(subparser):
    """
    %(prog)s [options] <directory> [...]
    %(prog)s --help
    """

    parser = subparser.add_parser("shell", help = "Start a new shell in the build environment", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build directory",
        metavar = "<directory>",
        action  = store_volume("build"))

    # Register runner flags and arguments; excludes ambient and AWS Batch
    # runners since those don't make any sense here.
    runner.register_runners(
        parser,
        exec    = ["bash", ...],
        runners = [docker, conda])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    overlay_volumes = [v for v in opts.volumes if v is not opts.build]

    if overlay_volumes and opts.__runner__ is not docker:
        raise UserError(f"""
            The {runner_name(opts.__runner__)} runtime does not support overlays (e.g. of {overlay_volumes[0].name}).
            Use the Docker runtime (--docker) if overlays are necessary.
            """)

    print(colored("bold", "Entering the Nextstrain build environment"))
    print()

    if opts.volumes and opts.__runner__ is docker:
        print(colored("bold", "Mapped volumes:"))

        # This is more tightly coupled to the Docker runner than I'd like (i.e.
        # assuming /nextstrain/…), but right now that's the only runner this
        # command supports (and the only one it makes sense to).
        #   -trs, 25 Sept 2018
        for volume in opts.volumes:
            print("  /nextstrain/%s is from %s" % (volume.name, volume.src.resolve(strict = True)))

        print()

    print(colored("bold", 'Run the command "exit" to leave the build environment.'))
    print()

    with resources.as_file("bashrc") as bashrc:
        # Ensure the history file exists to pass checks the Docker runner
        # performs for mounted volumes.  This also makes sure that the file is
        # writable by the Conda runtime too by ensuring the parent directory
        # exists.
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

        elif opts.__runner__ is docker:
            opts.volumes.append(NamedVolume("bashrc", bashrc, dir = False, writable = False))

            history_volume = NamedVolume("bash_history", history_file, dir = False)
            history_file = docker.mount_point(history_volume) # type: ignore[attr-defined] # for mypy
            opts.volumes.append(history_volume)

        extra_env = {
            "NEXTSTRAIN_PS1": ps1(),
            "NEXTSTRAIN_HISTFILE": str(history_file),
        }

        return runner.run(opts, working_volume = opts.build, extra_env = extra_env)


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

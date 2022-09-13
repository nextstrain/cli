"""
Start a new shell inside the Nextstrain containerized build environment to
run ad-hoc commands and perform debugging.

The shell runs inside a container, which requires Docker.  Run `nextstrain
check-setup` to check if Docker is installed and works.
"""

from typing import Tuple
from .. import resources
from .. import runner
from ..argparse import add_extended_help_flags
from ..runner import docker
from ..util import colored, remove_prefix, warn
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

    # Register runner flags and arguments; only Docker is supported for now
    # since a "native" shell doesn't make any sense.
    runner.register_runners(
        parser,
        exec    = ["bash", ...],
        runners = [docker])

    return parser


def run(opts):
    # Ensure our build dir exists
    if not opts.build.src.is_dir():
        warn("Error: Build path \"%s\" does not exist or is not a directory." % opts.build.src)

        if not opts.build.src.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    print(colored("bold", "Entering the Nextstrain build environment"))
    print()

    if opts.volumes:
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
        opts.volumes.append(NamedVolume("bashrc", bashrc, dir = False, writable = False))
        extra_env = {
            "NEXTSTRAIN_PS1": ps1(),
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

import argparse
import builtins
from argparse import ArgumentParser
from textwrap import dedent
from typing import cast, Mapping, List, Union, TYPE_CHECKING
from . import (
    docker as __docker,
    native as __native,
    aws_batch as __aws_batch,
)
from .. import config
from ..types import Options, RunnerModule
from ..util import runner_name, runner_help, warn
from ..volume import NamedVolume


# While PEP-0544 allows for modules to serve as implementations of Protocols¹,
# Mypy doesn't currently support it².  Pyright does³, however, so we tell Mypy
# to "trust us", but let Pyright actually check our work.  Mypy considers the
# MYPY variable to always be True when evaluating the code, regardless of the
# assignment below.
#
# This bit of type checking chicanery is not ideal, but the benefit of having
# our module interfaces actually checked by Pyright is worth it.  In the
# future, we should maybe ditch Mypy in favor of Pyright alone, but I didn't
# want to put in the due diligence for a full switchover right now.
#
#   -trs, 12 August 2021
#
# ¹ https://www.python.org/dev/peps/pep-0544/#modules-as-implementations-of-protocols
# ² https://github.com/python/mypy/issues/5018
# ³ https://github.com/microsoft/pyright/issues/1341
#
MYPY = False
if TYPE_CHECKING and MYPY:
    docker = cast(RunnerModule, __docker)
    native = cast(RunnerModule, __native)
    aws_batch = cast(RunnerModule, __aws_batch)
else:
    docker = __docker
    native = __native
    aws_batch = __aws_batch


all_runners: List[RunnerModule] = [
    docker,
    native,
    aws_batch,
]

all_runners_by_name = dict((runner_name(r), r) for r in all_runners)

default_runner = docker
configured_runner = config.get("core", "runner")

if configured_runner:
    if configured_runner in all_runners_by_name:
        default_runner = all_runners_by_name[configured_runner]
    else:
        warn("WARNING: Default runner from config file (%s) is invalid.  Using %s.\n"
            % (configured_runner, runner_name(default_runner)))


RunnerExec = List[Union[str, 'builtins.ellipsis']]


def register_runners(parser:  ArgumentParser,
                     exec:    RunnerExec,
                     runners: List[RunnerModule] = all_runners,
                     default: RunnerModule       = default_runner) -> None:
    """
    Register runner selection flags and runner-specific arguments on the given
    ArgumentParser instance.
    """
    # Not all commands may support the default runner.
    if default not in runners:
        default = runners[0]

    register_flags(parser, runners, default)
    register_arguments(parser, runners, exec = exec)


def register_flags(parser: ArgumentParser, runners: List[RunnerModule], default: RunnerModule) -> None:
    """
    Register runner selection flags on the given ArgumentParser instance.
    """
    runner_selection = parser.add_argument_group(
        "runner selection options",
        "Select the method for running a Nextstrain computing environment, if the\n"
        "default is not suitable.")

    # We use a different flag for each runner for a simpler UX, but only one
    # runner may be selected from the group.
    flags = runner_selection.add_mutually_exclusive_group()

    # The selected runner is stored in __runner__ (a la __command__).  The
    # run() function below calls __runner__.
    flags.set_defaults( __runner__ = default )

    # Add a flag for each runner based on its name.
    #
    # The standard display of option defaults (via ArgumentDefaultsHelpFormatter)
    # is suppressed so we can provide better custom handling that doesn't
    # expose full runner module names.
    for runner in runners:
        if runner is default:
            default_indicator = " (default)"
        else:
            default_indicator = ""

        flags.add_argument(
            "--%s" % runner_name(runner),
            help    = runner_help(runner) + default_indicator,
            action  = "store_const",
            const   = runner,
            dest    = "__runner__",
            default = argparse.SUPPRESS)


def register_arguments(parser: ArgumentParser, runners: List[RunnerModule], exec: RunnerExec) -> None:
    """
    Register arguments shared by all runners as well as runner-specific
    arguments on the given ArgumentParser instance.
    """

    # Unpack exec parameter into the command and everything else
    (exec_cmd, *exec_args) = exec

    # Arguments for all runners
    development = parser.add_argument_group(
        "development options",
        "These should generally be unnecessary unless you're developing Nextstrain.")

    # Image to use; shared by Docker and AWS Batch runners
    development.add_argument(
        "--image",
        help    = "Container image name to use for the Nextstrain computing environment",
        metavar = "<image>",
        default = docker.DEFAULT_IMAGE) # type: ignore

    # Program to execute
    #
    # XXX TODO: We could make this nargs = "*" to accept more than one arg and
    # thus provide a way to override default_exec_args.  This would resolve
    # some weirdness below re: the interplay of default exec args, the
    # Ellipsis, and extra_exec_args.  However, it would require --exec's last
    # value is followed by either another option or "--" to separate the --exec
    # values from other positional arguments like the build workdir.
    #   -trs, 21 May 2020
    development.add_argument(
        "--exec",
        help    = "Program to run inside the build environment",
        metavar = "<prog>",
        default = exec_cmd)

    # Static exec arguments; never modified directly by the user invocation,
    # but they won't be used if --exec is changed.
    parser.set_defaults(default_exec_cmd = exec_cmd)
    parser.set_defaults(default_exec_args = exec_args)

    # Optional exec arguments, if the calling command indicates they're allowed
    parser.set_defaults(extra_exec_args = [])

    if ... in exec_args:
        parser.add_argument(
            "extra_exec_args",
            help    = "Additional arguments to pass to the executed program",
            metavar = "...",
            nargs   = argparse.REMAINDER)

    # Register additional arguments for each runner
    for runner in runners:
        runner.register_arguments(parser)


def run(opts: Options, working_volume: NamedVolume = None, extra_env: Mapping = {}, cpus: int = None, memory: int = None) -> int:
    """
    Inspect the given options object and call the selected runner's run()
    function with appropriate arguments.
    """

    # Construct the appropriate argv list so each runner doesn't have to.  This
    # keeps together the definition of these options, above, and their
    # handling, below.
    argv = [
        opts.exec,
        *replace_ellipsis(
            opts.default_exec_args if opts.default_exec_cmd == opts.exec else [...],
            opts.extra_exec_args
        )
    ]

    if (opts.image != docker.DEFAULT_IMAGE # type: ignore
    and opts.__runner__ is native):
        warn(dedent("""
            Warning: The specified --image=%s option is not used by --native.
            """ % opts.image))

    return opts.__runner__.run(opts, argv, working_volume = working_volume, extra_env = extra_env, cpus = cpus, memory = memory)


def replace_ellipsis(items, elided_items):
    """
    Replaces any Ellipsis items (...) in a list, if any, with the items of a
    second list.
    """
    return [
        y for x in items
          for y in (elided_items if x is ... else [x])
    ]

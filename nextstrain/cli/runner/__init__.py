import argparse
from argparse import ArgumentParser
from typing import Any, Mapping, List
from . import docker, native, aws_batch
from .. import config
from ..types import Options
from ..util import runner_name, runner_help, warn
from ..volume import NamedVolume

all_runners = [
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


# The types of "runners" and "default" are left vague because a generic
# parameterization isn't easily possible with default values, as reported
# https://github.com/python/mypy/issues/3737.  The workaround becomes pretty
# sticky pretty quick for our use case, making it not worth it in my
# estimation.  It'd make things more confusing rather than more clear.
#
# Additionally, there seems to be no way to use the structural/duck typing
# provided by the Protocol type to annotate a _module_ type with attributes
# instead of a _class_.  Oh well.
#   -trs, 15 August 2018

def register_runners(parser:  ArgumentParser,
                     exec:    List,
                     runners: List = all_runners,
                     default: Any  = default_runner) -> None:
    """
    Register runner selection flags and runner-specific arguments on the given
    ArgumentParser instance.
    """
    # Not all commands may support the default runner.
    if default not in runners:
        default = runners[0]

    register_flags(parser, runners, default)
    register_arguments(parser, runners, exec = exec)


def register_flags(parser: ArgumentParser, runners: List, default: Any) -> None:
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


def register_arguments(parser: ArgumentParser, runners: List, exec: List) -> None:
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

    # Program to execute
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


def run(opts: Options, working_volume: NamedVolume = None, extra_env: Mapping = {}) -> int:
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

    return opts.__runner__.run(opts, argv, working_volume = working_volume, extra_env = extra_env)


def replace_ellipsis(items, elided_items):
    """
    Replaces any Ellipsis items (...) in a list, if any, with the items of a
    second list.
    """
    return [
        y for x in items
          for y in (elided_items if x is ... else [x])
    ]

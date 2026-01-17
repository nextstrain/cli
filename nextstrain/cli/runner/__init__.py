import argparse
import os
from argparse import ArgumentParser, ArgumentTypeError
from typing import List, TypeAlias, Union
from . import docker, conda, singularity, ambient, aws_batch
from .. import config, env, hostenv
from ..argparse import DirectoryPath, SKIP_AUTO_DEFAULT_IN_HELP
from ..errors import UserError
from ..types import EllipsisType, Env, Options, RunnerModule
from ..util import prose_list, runner_name, runner_module, runner_help, warn
from ..volume import store_volume, NamedVolume


all_runners: List[RunnerModule] = [
    docker,
    conda,
    singularity,
    ambient,
    aws_batch,
]

all_runners_by_name = dict((runner_name(r), r) for r in all_runners)

def runner_defaults():
    default_runner = docker
    configured_runner = None

    if configured := config.get("core", "runner"):
        try:
            configured_runner = runner_module(configured)
        except ValueError:
            warn("WARNING: Default runner from config file (%s) is invalid.  Using %s.\n"
                % (configured, runner_name(default_runner)))
        else:
            default_runner = configured_runner

    return default_runner, configured_runner

default_runner, configured_runner = runner_defaults()


RunnerExec: TypeAlias = List[Union[str, EllipsisType]]


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
        "runtime selection options",
        "Select the Nextstrain runtime to use, if the\n"
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

        if runner is ambient:
            # Alias --ambient as --native for backwards compatibility but hide
            # it from --help output.
            flags.add_argument(
                "--native",
                help    = argparse.SUPPRESS,
                action  = "store_const",
                const   = ambient,
                dest    = "__runner__")


def register_arguments(parser: ArgumentParser, runners: List[RunnerModule], exec: RunnerExec) -> None:
    """
    Register arguments shared by all runners as well as runner-specific
    arguments on the given ArgumentParser instance.
    """

    # Unpack exec parameter into the command and everything else
    (exec_cmd, *exec_args) = exec

    # Arguments for all runners
    runtime = parser.add_argument_group(
        "runtime options",
        "Options shared by all runtimes.")

    runtime.add_argument(
        "--env",
        metavar = "<name>[=<value>]",
        help    = "Set the environment variable ``<name>`` to the value in the current environment (i.e. pass it thru) or to the given ``<value>``. "
                  "May be specified more than once. "
                  "Overrides any variables of the same name set via :option:`--envdir`. "
                  "When this option or :option:`--envdir` is given, the default behaviour of automatically passing thru several \"well-known\" variables is disabled. "
                  f"The \"well-known\" variables are {prose_list([f'``{x}``' for x in hostenv.forwarded_names], 'and')}. "
                  "Pass those variables explicitly via :option:`--env` or :option:`--envdir` if you need them in combination with other variables. "
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        action  = "append",
        default = [])

    runtime.add_argument(
        "--envdir",
        metavar = "<path>",
        help    = "Set environment variables from the envdir at ``<path>``. "
                  "May be specified more than once. "
                  "An envdir is a directory containing files describing environment variables. "
                  "Each filename is used as the variable name. "
                  "The first line of the contents of each file is used as the variable value. "
                  "When this option or :option:`--env` is given, the default behaviour of automatically passing thru several \"well-known\" variables is disabled. "
                  f"Envdirs may also be specified by setting ``NEXTSTRAIN_RUNTIME_ENVDIRS`` in the environment to a ``{os.pathsep}``-separated list of paths. "
                  "See the description of :option:`--env` for more details. "
                  f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        type    = DirectoryPath,
        action  = "append",
        default = [])

    # Development arguments for all runners
    development = parser.add_argument_group(
        "development options",
        "These should generally be unnecessary unless you're developing Nextstrain.")

    # Image to use; shared by Docker, AWS Batch, and Singularity runners
    development.add_argument(
        "--image",
        help    = "Container image name to use for the Nextstrain runtime "
                  f"(default: %(default)s for Docker and AWS Batch, {singularity.DEFAULT_IMAGE} for Singularity)",
        metavar = "<image>",
        default = docker.DEFAULT_IMAGE)

    development.set_defaults(volumes = [])

    for name in docker.COMPONENTS:
        development.add_argument(
            "--" + name,
            help    = "Replace the image's copy of %s with a local copy" % name,
            metavar = "<dir>",
            action  = store_volume(name))

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
        help    = "Program to run inside the runtime",
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


def run(opts: Options, working_volume: NamedVolume = None, extra_env: Env = {}, cpus: int = None, memory: int = None) -> int:
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

    if (opts.image is not docker.DEFAULT_IMAGE
    and opts.__runner__ in {conda, ambient}):
        why_runner = "the configured default" if default_runner in {conda, ambient} else f"selected by --{runner_name(opts.__runner__)}"
        raise UserError(f"""
            The --image option is incompatible with the {runner_name(opts.__runner__)} runtime ({why_runner}).

            If you need to use the {runner_name(opts.__runner__)} runtime, please omit the --image option.

            If you need the --image option, please select another runtime (e.g.
            with the --docker option) that supports it.  Currently --image is
            supported by the Docker (--docker), AWS Batch (--aws-batch), and
            Singularity (--singularity) runtimes.  You can check if your setup
            supports these runtimes with `nextstrain check-setup`.
            """)

    # Account for potentially different defaults for --image depending on the
    # selected runner.
    if opts.__runner__ is singularity and opts.image is docker.DEFAULT_IMAGE:
        opts.image = singularity.DEFAULT_IMAGE

    if envdirs := os.environ.get("NEXTSTRAIN_RUNTIME_ENVDIRS"):
        try:
            opts.envdir = [
                *[DirectoryPath(d) for d in envdirs.split(os.pathsep) if d],
                *opts.envdir ]
        except ArgumentTypeError as err:
            raise UserError(f"{err} (in NEXTSTRAIN_RUNTIME_ENVDIRS)")

    # Add env from automatically forwarded vars xor from --envdir and --env
    # without overriding values explicitly set by our commands' own internals
    # (i.e. the callers of this function).
    if opts.envdir or opts.env:
        extra_env = {
            **dict(env.from_dirs(opts.envdir)),
            **dict(env.from_vars(opts.env)),
            **extra_env }
    else:
        extra_env = {
            **dict(hostenv.forwarded_values()),
            **extra_env }

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

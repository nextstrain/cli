"""
Checks for supported runtimes.

Five runtimes are tested by default:

  • Our Docker image is the preferred runtime.  Docker itself must
    be installed and configured on your computer first, but once it is, the
    runtime is robust and reproducible.

  • Our Conda runtime will be tested for existence and appearance of
    completeness. This runtime is more isolated and reproducible than your
    ambient runtime, but is less isolated and robust than the Docker
    runtime.

  • Our Singularity runtime uses the same container image as our Docker
    runtime.  Singularity must be installed and configured on your computer
    first, although it is often already present on HPC systems.  This runtime
    is more isolated and reproducible than the Conda runtime, but potentially
    less so than the Docker runtime.

  • Your ambient setup will be tested for snakemake, augur, and auspice.
    Their presence implies a working runtime, but does not guarantee
    it.

  • Remote jobs on AWS Batch.  Your AWS account, if credentials are available
    in your environment or via aws-cli configuration, will be tested for the
    presence of appropriate resources.  Their presence implies a working AWS
    Batch runtime, but does not guarantee it.

Provide one or more runtime names as arguments to test just those instead.

Exits with an error code if the default runtime ({default_runner_name}) is not
supported or, when the default runtime is omitted from checks, if none of the
checked runtimes are supported.
"""

from functools import partial
from .. import config
from ..argparse import SKIP_AUTO_DEFAULT_IN_HELP, runner_module_argument
from ..types import Options
from ..util import colored, check_for_new_version, runner_name, runner_tests_ok, print_runner_tests
from ..runner import all_runners, all_runners_by_name, default_runner # noqa: F401 (it's wrong; we use it in run())


__doc__ = (__doc__ or "").format(default_runner_name = runner_name(default_runner))


def register_parser(subparser):
    parser = subparser.add_parser("check-setup", help = "Check runtime setups")

    parser.add_argument(
        "runners",
        help     = "The Nextstrain runtimes to check. "
                   f"(default: {', '.join(all_runners_by_name)})"
                   f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        metavar  = "<runtime>",
        nargs    = "*",
        type     = runner_module_argument,
        default  = all_runners)

    parser.add_argument(
        "--set-default",
        help   = "Set the default runtime to the first which passes check-setup. "
                 "Checks run in the order given, if any, "
                 "otherwise in the default order: %s." % (", ".join(all_runners_by_name),),
        action = "store_true")

    return parser


def run(opts: Options) -> int:
    global default_runner

    success = partial(colored, "green")
    failure = partial(colored, "red")

    # Check our own version for updates
    check_for_new_version()

    # Run and collect our runners' self-tests
    print("Testing your setup…")

    runner_tests = [
        (runner, runner.test_setup())
            for runner in opts.runners
    ]

    runner_status = {
        runner: runner_tests_ok(tests)
            for runner, tests in runner_tests
    }

    # Print test results.  The first print() separates results from the
    # previous header or stderr output, making it easier to read.
    print()

    for runner, tests in runner_tests:
        if runner_status[runner]:
            supported = success("supported")
        else:
            supported = failure("not supported")

        print(colored("blue", "#"), "%s is %s" % (runner_name(runner), supported))
        print_runner_tests(tests)
        print()

    # Print overall status.
    supported_runners = [
        runner
            for runner, status_ok in runner_status.items()
             if status_ok
    ]

    if supported_runners:
        print("Supported Nextstrain runtimes:", ", ".join(success(runner_name(r)) for r in supported_runners))

        if opts.set_default:
            default_runner = supported_runners[0]
            print()
            print("Setting default runtime to %s." % runner_name(default_runner))
            config.set("core", "runner", runner_name(default_runner))
            default_runner.set_default_config()
    else:
        if set(opts.runners) == set(all_runners):
            print(failure("No support for any Nextstrain runtime."))
        else:
            print(failure("No support for selected Nextstrain runtimes."))

    print()
    if default_runner in supported_runners:
        print(f"All good!  Default runtime ({runner_name(default_runner)}) is supported.")
    else:
        if default_runner in opts.runners:
            print(failure(f"No good.  Default runtime ({runner_name(default_runner)}) is not supported."))
        else:
            print(f"Warning: Support for the default runtime ({runner_name(default_runner)}) was not checked.")

        if supported_runners and not opts.set_default:
            print()
            print("Try running check-setup again with the --set-default option to pick a supported runtime above.")

    # Return a 1 or 0 exit code
    if default_runner in opts.runners:
        return 0 if default_runner in supported_runners else 1
    else:
        return 0 if supported_runners else 1

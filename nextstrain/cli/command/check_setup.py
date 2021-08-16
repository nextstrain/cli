"""
Checks your local setup to see if you have a supported build environment.

Three environments are supported, each of which will be tested:

  • Our Docker image is the preferred build environment.  Docker itself must
    be installed and configured on your computer first, but once it is, the
    build environment is robust and reproducible.

  • Your native ambient environment will be tested for snakemake, augur, and
    auspice. Their presence implies a working build environment, but does not
    guarantee it.

  • Remote jobs on AWS Batch.  Your AWS account, if credentials are available
    in your environment or via aws-cli configuration, will be tested for the
    presence of appropriate resources.  Their presence implies a working AWS
    Batch environment, but does not guarantee it.
"""

from functools import partial
from textwrap import indent
from .. import config
from ..types import Options
from ..util import colored, check_for_new_version, remove_prefix, runner_name
from ..runner import all_runners


def register_parser(subparser):
    parser = subparser.add_parser("check-setup", help = "Test your local setup")

    parser.add_argument(
        "--set-default",
        help   = "Set the default environment to the first which passes check-setup. Checks run in the order: %s." % (", ".join(map(runner_name, all_runners)),),
        action = "store_true")

    return parser


def run(opts: Options) -> int:
    success = partial(colored, "green")
    failure = partial(colored, "red")
    warning = partial(colored, "yellow")
    unknown = partial(colored, "gray")

    # XXX TODO: Now that there are special values other than True/False, these
    # should probably become an enum or custom algebraic type or something
    # similar.  That will cause a cascade into the test_setup() producers
    # though, which I'm going to punt on for now.
    #  -trs, 4 Oct 2018
    status = {
        True:  success("✔ yes"),
        False: failure("✘ no"),
        None:  warning("⚑ warning"),
        ...:   unknown("? unknown"),
    }

    # Check our own version for updates
    check_for_new_version()

    # Run and collect our runners' self-tests
    print("Testing your setup…")

    runner_tests = [
        (runner, runner.test_setup())
            for runner in all_runners
    ]

    runner_status = {
        runner: False not in [result for test, result in tests]
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

        for description, result in tests:
            # Indent subsequent lines of any multi-line descriptions so it
            # lines up under the status marker.
            formatted_description = \
                remove_prefix("  ", indent(description, "  "))

            print(status.get(result, str(result)) + ":", formatted_description)

        print()

    # Print overall status.
    supported_runners = [
        runner_name(runner)
            for runner, status_ok in runner_status.items()
             if status_ok
    ]

    if supported_runners:
        print("All good!  Supported Nextstrain environments:", ", ".join(map(success, supported_runners)))

        if opts.set_default:
            print()
            print("Setting default environment to %s." % supported_runners[0])
            config.set("core", "runner", supported_runners[0])
    else:
        print(failure("No good.  No support for any Nextstrain environment."))

    # Return a 1 or 0 exit code
    return int(not supported_runners)

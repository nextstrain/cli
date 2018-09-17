"""
Checks your local setup to see if you have a supported build environment.

Three environments are supported, each of which will be tested:

  • Our Docker image is the preferred build environment.  Docker itself must
    be installed and configured on your computer first, but once it is, the
    build environment is robust and reproducible.

  • Your native ambient environment will be tested for snakemake and augur.
    Their presence implies a working build environment, but does not guarantee
    it.

  • Remote jobs on AWS Batch.  Your AWS account, if credentials are available
    in your environment or via aws-cli configuration, will be tested for the
    presence of appropriate resources.  Their presence implies a working AWS
    Batch environment, but does not guarantee it.
"""

from functools import partial
from ..util import colored, check_for_new_version, runner_name
from ..runner import all_runners


def register_parser(subparser):
    parser = subparser.add_parser("check-setup", help = "Test your local setup")
    return parser


def run(opts):
    success = partial(colored, "green")
    failure = partial(colored, "red")

    status = {
        True:  success("✔"),
        False: failure("✘"),
    }

    # Check our own version for updates
    check_for_new_version()

    # Run and collect our runners' self-tests
    print("Testing your setup…")

    runner_tests = [
        (runner, runner.test_setup())
            for runner in all_runners
    ]

    # Print test results.  The first print() separates results from the
    # previous header or stderr output, making it easier to read.
    print()

    for runner, tests in runner_tests:
        print(colored("blue", "#"), "%s support" % runner_name(runner))

        for description, result in tests:
            print(status.get(result, " "), description)

        print()

    # Print overall status.
    runner_status = [
        (runner, False not in [result for test, result in tests])
            for runner, tests in runner_tests
    ]

    supported_runners = [
        runner_name(runner)
            for runner, status_ok in runner_status
             if status_ok
    ]

    if supported_runners:
        print(success("Supported runners: %s" % ", ".join(supported_runners)))
    else:
        print(failure("No support for any runner"))

    # Return a 1 or 0 exit code
    return int(not supported_runners)

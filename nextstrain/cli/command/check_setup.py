"""
Checks your local setup to make sure a container runner is installed and works.

Docker is the currently the only supported container system.  It must be
installed and configured, which this command will test by running:

    docker run --rm hello-world

"""

from functools import partial
from ..util import colored
from ..runner import all_runners


def register_parser(subparser):
    parser = subparser.add_parser("check-setup", help = "Tests your local setup")
    parser.description = __doc__
    return parser


def run(opts):
    success = partial(colored, "green")
    failure = partial(colored, "red")

    status = {
        True:  success("✔"),
        False: failure("✘"),
    }

    # Run and collect our runners' self-tests
    print("Testing your setup…")

    tests = [
        test for runner in all_runners
             for test in runner.test_setup()
    ]

    # Print test results.  The first print() separates results from the
    # previous header or stderr output, making it easier to read.
    print()

    for description, result in tests:
        print(status.get(result, " "), description)

    # Print overall status
    all_good = False not in [result for description, result in tests]

    print()
    print(success("All good!") if all_good else failure("Some setup tests failed"))

    # Return a 1 or 0 exit code
    return int(not all_good)

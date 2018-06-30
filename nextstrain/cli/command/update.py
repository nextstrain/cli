"""
Updates your local copy of the default container image.

This may take several minutes as the layers of the image are downloaded.
"""

from functools import partial
from ..util import colored
from ..runner import all_runners


def register_parser(subparser):
    parser = subparser.add_parser("update", help = "Updates your local image copy")
    parser.description = __doc__
    return parser


def run(opts):
    success = partial(colored, "green")
    failure = partial(colored, "red")

    statuses = [
        runner.update()
            for runner in all_runners
    ]

    # Print overall status
    all_good = False not in statuses

    print()
    print(success("Up to date!") if all_good else failure("Update failed"))

    # Return a 1 or 0 exit code
    return int(not all_good)

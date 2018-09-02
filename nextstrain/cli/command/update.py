"""
Updates your local copy of the default container image.

This may take several minutes as the layers of the image are downloaded.
"""

from functools import partial
from ..util import colored, check_for_new_version
from ..runner import all_runners


def register_parser(subparser):
    parser = subparser.add_parser("update", help = "Update your local image copy")
    return parser


def run(opts):
    # Check our own version for updates
    newer_version = check_for_new_version()

    success = partial(colored, "green")
    failure = partial(colored, "red")
    notice  = partial(colored, "yellow")

    statuses = [
        runner.update()
            for runner in all_runners
    ]

    # Print overall status
    all_good = False not in statuses

    if all_good:
        print()
        print(success("Your images are up to date!"))
        if newer_version:
            print()
            print(notice("…but consider upgrading nextstrain-cli too, as noted above."))
    else:
        print()
        print(failure("Updating images failed"))
        if newer_version:
            print()
            print(notice("Maybe upgrading nextstrain-cli, as noted above, will help?"))

    # Return a 1 or 0 exit code
    return int(not all_good)

"""
Updates a Nextstrain runtime to the latest available version, if any.

The default runtime ({default_runner_name}) is updated when this command is run
without arguments.  Provide a runtime name as an argument to update a specific
runtime instead.

Only two runtimes currently support updates: Docker and Conda.  Both may take
several minutes as new software versions are downloaded.

This command also checks for newer versions of the Nextstrain CLI (the
``nextstrain`` program) itself and will suggest upgrade instructions if an
upgrade is available.
"""
from functools import partial
from ..argparse import runner_module_argument, SKIP_AUTO_DEFAULT_IN_HELP
from ..util import colored, check_for_new_version, runner_name
from ..runner import all_runners_by_name, default_runner


__doc__ = (__doc__ or "").format(default_runner_name = runner_name(default_runner))


def register_parser(subparser):
    parser = subparser.add_parser("update", help = "Update a runtime")

    parser.add_argument(
        "runner",
        help     = "The Nextstrain build environment (aka Nextstrain runtime) to check. "
                   f"One of {{{', '.join(all_runners_by_name)}}}. "
                   f"(default: {runner_name(default_runner)})"
                   f"{SKIP_AUTO_DEFAULT_IN_HELP}",
        metavar  = "<runtime>",
        nargs    = "?",
        type     = runner_module_argument,
        default  = default_runner)

    return parser


def run(opts):
    heading = partial(colored, "bold")
    success = partial(colored, "green")
    failure = partial(colored, "red")
    notice  = partial(colored, "yellow")

    # Check our own version for updates
    print(heading(f"Checking for newer versions of Nextstrain CLI…"))
    print()
    newer_version = check_for_new_version()

    # Perform update
    print(heading(f"Updating {runner_name(opts.runner)} runtime…"))
    ok = opts.runner.update()

    # Print overall status
    if ok:
        print()
        print(success("Runtime updated!"))
        if newer_version:
            print()
            print(notice("…but consider upgrading Nextstrain CLI too, as noted above."))
    else:
        print()
        if ok is None:
            print(failure("Runtime doesn't support updating."))
        else:
            print(failure("Updating failed!"))
        if newer_version:
            print()
            print(notice("Maybe upgrading Nextstrain CLI, as noted above, will help?"))

    # Return a 1 or 0 exit code
    return int(not ok)

"""
Sets up a Nextstrain pathogen or runtime for use with `nextstrain run`,
`nextstrain build`, `nextstrain view`, etc.

For pathogens, TKTK

For runtimes, only the Conda runtime currently supports fully-automated set up,
but this command may still be used with other runtimes to check an existing
(manual) setup and set the runtime as the default on success.

Exits with an error code if automated set up fails or if setup checks fail.
"""
# XXX FIXME doc above
from functools import partial
from textwrap import dedent

from .. import console
from ..errors import UserError
from ..util import colored, runner_module, runner_name, setup_tests_ok, print_setup_tests
from ..types import Options
from ..runner import all_runners_by_name, configured_runner, default_runner # noqa: F401 (it's wrong; we use it in run())
from ..workflows import PathogenWorkflows, pathogen_default_version


heading = partial(colored, "bold")
failure = partial(colored, "red")


def register_parser(subparser):
    """
    %(prog)s [--dry-run] [--force] [--set-default] <pathogen|runtime>
    %(prog)s --help
    """
    parser = subparser.add_parser("setup", help = "Set up a pathogen or runtime")

    parser.add_argument(
        "thing",
        help     = "The Nextstrain pathogen or runtime to set up. "
                   f"A runtime is one of {{{', '.join(all_runners_by_name)}}}. "
                   "A pathogen is either the name of a Nextstrain-maintained pathogen (e.g. measles) or a URL to a ZIP file (e.g. https://github.com/nextstrain/measles/archive/refs/heads/main.zip).",
                   # XXX FIXME: pathogen@version syntax
        metavar  = "<pathogen|runtime>")

    parser.add_argument(
        "--dry-run",
        help   = "Don't actually set up anything, just show what would happen.",
        action = "store_true")

    parser.add_argument(
        "--force",
        help    = "Ignore existing setup, if any, and always start fresh.",
        action  = "store_true",
        default = False)

    parser.add_argument(
        "--set-default",
        help   = "Use this pathogen version or runtime as the default if set up is successful.",
        action = "store_true")

    return parser


@console.auto_dry_run_indicator()
def run(opts: Options) -> int:
    global default_runner

    try:
        kind    = "runtime"
        thing   = runner_module(opts.thing)
        nameof  = runner_name
        default = default_runner

    except ValueError as e1:
        try:
            kind    = "pathogen"
            thing   = PathogenWorkflows(opts.thing, new_setup = True)
            nameof  = str

            # XXX FIXME
            if default_version := pathogen_default_version(thing.name, implicit = False):
                default = PathogenWorkflows(thing.name, default_version)
            else:
                default = None

        except ValueError as e2:
            raise UserError(f"""
                No valid runtime nor pathogen given:

                  • {e1}
                  • {e2}
                """)

    # Setup
    print(heading(f"Setting up {nameof(thing)}…"))
    setup_ok = thing.setup(dry_run = opts.dry_run, force = opts.force)

    if setup_ok is None:
        print("Automated set up is not supported, but we'll check for a manual setup.")
    elif not setup_ok:
        print()
        print(failure("Set up failed!"))
        return 1

    # Test
    print()
    print(heading(f"Checking setup…"))

    if not opts.dry_run:
        tests = thing.test_setup()

        print_setup_tests(tests)

        if not setup_tests_ok(tests):
            print()
            print(failure("Checks failed!  Setup is unlikely to be fully functional."))
            return 1
    else:
        print("Skipping checks for dry run.")

    # Optionally set as default
    if opts.set_default:
        default = thing
        print()
        print(f"Setting {kind} default to {nameof(default)}.")

        if not opts.dry_run:
            default.set_default_config()

    # Warn if this isn't the default
    if default != thing:
        if kind == "runtime":
            print()
            if not configured_runner:
                print(f"Warning: No default runtime is configured so {runner_name(default_runner)} will be used.")
            else:
                print(f"Note that your default runtime is still {runner_name(default_runner)}.")
            print()
            print(dedent(f"""\
                You can use {runner_name(opts.runner)} on an ad-hoc basis with commands
                like `nextstrain run`, `nextstrain build`, `nextstrain view`, etc. by
                passing them the --{runner_name(opts.runner)} option, e.g.:

                    nextstrain build --{runner_name(opts.runner)} …

                If you want to use {runner_name(opts.runner)} by default instead, re-run
                this command with the --set-default option, e.g.:

                    nextstrain setup --set-default {runner_name(opts.runner)}\
                """))

        elif kind == "pathogen":
            # XXX FIXME
            ...
            

    print()
    print("All good!  Set up of", nameof(thing), "complete.")
    return 0

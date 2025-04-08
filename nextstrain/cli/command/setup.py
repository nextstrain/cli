"""
Sets up a Nextstrain pathogen for use with `nextstrain run` or a Nextstrain
runtime for use with `nextstrain run`, `nextstrain build`, `nextstrain view`,
etc.

For pathogens, set up involves downloading a specific version of the pathogen's
Nextstrain workflows.  By convention, this download is from Nextstrain's
repositories.  More than one version of the same pathogen may be set up and
used independently.  This can be useful for comparing analyses across workflow
versions.  A default version can be set.

For runtimes, only the Conda runtime currently supports fully-automated set up,
but this command may still be used with other runtimes to check an existing
(manual) setup and set the runtime as the default on success.

Exits with an error code if automated set up fails or if setup checks fail.
"""
from functools import partial
from inspect import cleandoc
from textwrap import dedent, indent
from typing import Union

from .. import console
from ..errors import UserError
from ..util import colored, runner_module, runner_name, print_and_check_setup_tests
from ..types import Options, RunnerModule, SetupTestResults
from ..pathogens import PathogenVersion, pathogen_defaults
from ..runner import all_runners_by_name, runner_defaults



heading = partial(colored, "bold")
failure = partial(colored, "red")


def register_parser(subparser):
    """
    %(prog)s [--dry-run] [--force] [--set-default] <pathogen-name>[@<version>[=<url>]]
    %(prog)s [--dry-run] [--force] [--set-default] <runtime-name>
    %(prog)s --help
    """
    parser = subparser.add_parser("setup", help = "Set up a pathogen or runtime")

    parser.add_argument(
        "arg",
        help = dedent(f"""\
            The Nextstrain pathogen or runtime to set up.

            A pathogen is usually the plain name of a Nextstrain-maintained
            pathogen (e.g. ``measles``), optionally with an ``@<version>``
            specifier (e.g. ``measles@v42``).  If ``<version>`` is specified in
            this case, it must be a tag name (i.e. a release name), development
            branch name, or a development commit id.

            A pathogen may also be fully-specified as ``<name>@<version>=<url>``
            where ``<name>`` and ``<version>`` in this case are (mostly)
            arbitrary and ``<url>`` points to a ZIP file containing the
            pathogen repository contents (e.g.
            ``https://github.com/nextstrain/measles/zipball/83b446d67fc03de2ce1c72bb1345b4c4eace7231``).

            A runtime is one of {{{', '.join(all_runners_by_name)}}}.
            """),
        metavar = "<pathogen>|<runtime>")

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
    try:
        runner = runner_module(opts.arg)
    except ValueError as e1:
        try:
            pathogen = PathogenVersion(opts.arg, new_setup = True)
        except Exception as e2:
            raise UserError(f"""
                Unable to set up {opts.arg!r}.

                It's not a valid runtime:

                {{e1}}

                nor pathogen:

                {{e2}}

                as specified.  Double check your spelling and syntax?
                """, e1 = indent(str(e1), "    "), e2 = indent(str(e2), "    "))
        else:
            arg             = pathogen
            defaults        = partial(pathogen_defaults, pathogen.name)
            kind_of_default = "pathogen default version"
    else:
        arg             = runner
        defaults        = runner_defaults
        kind_of_default = "default runtime"

    # Setup
    print(heading(f"Setting up {nameof(arg)}…"))
    setup_ok = arg.setup(dry_run = opts.dry_run, force = opts.force)

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
        tests: SetupTestResults = arg.test_setup()

        ok = print_and_check_setup_tests(tests)

        if not ok:
            print()
            print(failure("Checks failed!  Setup is unlikely to be fully functional."))
            return 1
    else:
        print("Skipping checks for dry run.")

    # Optionally set as default
    if opts.set_default:
        print()
        print(f"Setting {kind_of_default} to {nameof(arg)}.")

        if not opts.dry_run:
            arg.set_default_config()

    # Evaluate defaults now, as the new setup may have configured a new default
    # (above) or changed the intuited implicit default.
    if opts.set_default and opts.dry_run:
        # Assume setting default works for sake of dry run.
        default = configured_default = arg
    else:
        # Otherwise, get real defaults.  But note that under a dry run that's
        # not setting the default too, this is likely to be incorrect when the
        # new setup we only pretended to do will in reality perturb the
        # implicit default.
        #
        # XXX TODO: Maybe fix the above with a state context object we can
        # update for dry run or mocks or something similar.  Not now, though.
        # This is a pervasive problem.
        #   -trs, 10 Jan 2025
        default, configured_default = defaults()

    assert not configured_default or default == configured_default, \
        f"{configured_default=} {default=}"

    # Warn if this isn't the default
    if default != arg:
        print()
        if not configured_default:
            if default:
                print(f"Warning: No {kind_of_default} is configured so {nameof(default)} (not {nameof(arg)}) will be used implicitly.")
            else:
                print(f"Warning: No {kind_of_default} is configured and no implicit default is intuitable.")
        else:
            assert default
            print(f"Note that your {kind_of_default} is still {nameof(default)}.")

        if kind_of_default == "default runtime":
            examples = cleandoc(f"""
                nextstrain run --{nameof(arg)} …
                nextstrain build --{nameof(arg)} …
                nextstrain view --{nameof(arg)} …
                """)
        elif kind_of_default == "pathogen default version":
            examples = cleandoc(f"""
                nextstrain run {nameof(arg)} …
                """)
        else:
            examples = None

        assert examples

        print()
        print(dedent(f"""\
            You can use {nameof(arg)} on an ad-hoc basis by specifying it
            explicitly, e.g.:

            {{examples}}

            If you want to use {nameof(arg)} by default instead, re-run
            this command with the --set-default option, e.g.:

                nextstrain setup --set-default {nameof(arg)}\
            """).format(examples = indent(examples, "    ")))

    # Warn about relying on implicit defaults
    if default and default == arg and not configured_default:
        print()
        print(f"Warning: No {kind_of_default} is configured but {nameof(default)} will be used implicitly.")
        print(f"Future changes (e.g. additional `nextstrain setup`s) may affect this implicit default.")
        print()
        print(dedent(f"""\
            If you want to use {nameof(arg)} by default regardless of future
            changes, re-run this command with the --set-default option, e.g.:

                nextstrain setup --set-default {nameof(arg)}\
            """))

    print()
    print("All good!  Set up of", nameof(arg), "complete.")
    return 0


# str(x) doesn't look for x.__str__ but type(x).__str__, which means we can't
# just define __str__ in a module have it be called by str(module).  We can't
# modify the module type either, so this function is necessary.
#   -trs, 25 Feb 2025
def nameof(arg: Union[RunnerModule, PathogenVersion]) -> str:
    if isinstance(arg, RunnerModule):
        return runner_name(arg)
    return str(arg)

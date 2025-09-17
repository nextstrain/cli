"""
Updates Nextstrain pathogens and runtimes to the latest available versions, if any.

When this command is run without arguments, the default version for each set up
pathogen ({default_pathogens}) and the default runtime ({default_runner_name})
are updated.  Provide one or more pathogens and/or runtimes as arguments to
update a select list instead.

Three runtimes currently support updates: Docker, Conda, and Singularity.
Updates may take several minutes as new software versions are downloaded.

This command also checks for newer versions of the Nextstrain CLI (the
`nextstrain` program) itself and will suggest updating if an new version is
available.  Running `nextstrain update cli` will automatically update to the
new version.
"""

import traceback
from functools import partial
from textwrap import dedent, indent
from typing import Callable, List, Tuple

from ..argparse import SKIP_AUTO_DEFAULT_IN_HELP
from ..debug import DEBUGGING
from ..errors import UserError
from ..util import colored, check_for_new_version, prose_list, runner_name, warn
from ..pathogens import every_pathogen_default_by_name, PathogenVersion
from ..runner import all_runners_by_name, default_runner, runner_module
from ..types import UpdateStatus


# Intentionally re-instantiate PathogenVersion objects without a version in the
# spec, for update().
default_pathogens = [
    PathogenVersion(name)
        for name in every_pathogen_default_by_name().keys() ]

__doc__ = (__doc__ or "").format(
    default_pathogens = (
        prose_list([f"``{p.name}``" for p in default_pathogens], "and")
            if default_pathogens else
        "none"
    ),
    default_runner_name = runner_name(default_runner),
)


def register_parser(subparser):
    """
    %(prog)s [<pathogen-name>[@<version>] | <runtime-name> […]]
    %(prog)s
    %(prog)s cli
    %(prog)s --help
    """
    parser = subparser.add_parser("update", help = "Update a pathogen or runtime (or this program)")

    parser.add_argument(
        "args",
        help = dedent(f"""\
            The Nextstrain pathogens and/or runtimes to update.

            A pathogen is the name (and optionally, version) of a previously
            set up pathogen.  See :command-reference:`nextstrain setup`.  If no
            version is specified, then the default version will be updated to
            the latest available version.

            A runtime is one of {{{', '.join(all_runners_by_name)}}}.

            {SKIP_AUTO_DEFAULT_IN_HELP}
            """),
        metavar = "<pathogen>|<runtime>",
        nargs   = "*")

    return parser


def run(opts):
    heading = partial(colored, "bold")
    success = partial(colored, "green")
    failure = partial(colored, "red")
    notice  = partial(colored, "yellow")

    update_self = False

    updates: List[Tuple[Callable[[], UpdateStatus], str]] = []

    if opts.args:
        for arg in opts.args:
            # Special case the arg used to update ourselves.
            if arg.lower() == "cli":
                update_self = True
                continue

            try:
                runner = runner_module(arg)
            except ValueError as e1:
                try:
                    pathogen = PathogenVersion(arg)
                except Exception as e2:
                    raise UserError(f"""
                        Unable to update {arg!r}.

                        It's not a valid runtime:

                        {{e1}}

                        nor pathogen:

                        {{e2}}

                        as specified.  Double check your spelling and syntax?
                        """, e1 = indent(str(e1), "    "), e2 = indent(str(e2), "    "))
                else:
                    if pathogen.spec.version:
                        updates += [(pathogen.update, f"{pathogen} pathogen version")]
                    else:
                        updates += [(pathogen.update, f"{pathogen.name} pathogen default version")]
            else:
                updates += [(runner.update, f"{runner_name(runner)} runtime")]
    else:
        # Pathogen default versions and default runtime.
        updates = [(p.update, f"{p.name} pathogen default version") for p in default_pathogens] \
                + [(default_runner.update, f"{runner_name(default_runner)} default runtime")]

    # Check our own version for updates
    new_version_check = check_for_new_version()

    if update_self:
        updates += [(new_version_check.update, "Nextstrain CLI")]
    else:
        print(heading(f"Checking for newer versions of Nextstrain CLI…"))
        print()
        print(new_version_check.status_message)
        # We'll re-print the update notice along with update instructions at
        # the bottom.

    # Perform updates
    if not updates:
        if new_version_check.newer_version:
            print(new_version_check.update_instructions)
            print("Nothing to update (except Nextstrain CLI itself, see above)!")
        else:
            print("Nothing to update!")
        return 0

    oks: List[UpdateStatus] = []

    for update, description in updates:
        print(heading(f"Updating {description}…"))

        try:
            ok = update()
        except Exception as err:
            ok = False

            if str(err):
                warn(str(err))
            if DEBUGGING:
                traceback.print_exc()

        oks.append(ok)

        if ok:
            print(success(f"Updated {description}!"))
        else:
            if ok is None:
                print(failure(f"Updating {description} is unsupported."))
            else:
                print(failure(f"Updating {description} failed!"))
        print()

    # Print overall status
    if all(oks):
        print(success("All updates successful!"))
        if not update_self and new_version_check.newer_version:
            print()
            print(notice("…but consider upgrading Nextstrain CLI too."))
            print()
            print(new_version_check.status_message)
            print(new_version_check.update_instructions)
    else:
        print(failure("Some updates failed!  See above for details."))
        if not update_self and new_version_check.newer_version:
            print()
            print(notice("Maybe upgrading Nextstrain CLI will help?"))
            print()
            print(new_version_check.status_message)
            print(new_version_check.update_instructions)

    # Return a 1 or 0 exit code
    return int(not all(oks))

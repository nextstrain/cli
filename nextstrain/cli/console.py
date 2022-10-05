"""
Console interface.
"""
import re
import sys
from contextlib import contextmanager, ExitStack, redirect_stdout, redirect_stderr
from functools import wraps
from typing import Callable, TextIO
from wrapt import ObjectProxy


def auto_dry_run_indicator(getter: Callable[..., bool] = lambda opts, *args, **kwargs: opts.dry_run):
    """
    Automatically wraps a function in a :py:func:`dry_run_indicator` context
    based on the function's arguments.

    *getter* is a callable which accepts any arguments and returns a boolean
    indicating if a dry run mode is active or not.

    The default *getter* is intended for the typical ``run(opts)`` functions of
    our command modules that use an ``opts.dry_run`` parameter (i.e. set by the
    ``--dry-run`` command-line option).  Provide a custom *getter* if that's
    not the case.

    The primary usefulness of this decorator is avoiding additional near-global
    levels of indentation.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get dry run status from function args
            dry_run = getter(*args, **kwargs)

            # Run under an indicator context
            with dry_run_indicator(dry_run):
                return f(*args, **kwargs)
        return decorated
    return decorator


@contextmanager
def dry_run_indicator(dry_run: bool = False):
    """
    Context manager to add an indication to :py:attr:`sys.stdout` and
    :py:attr:`sys.stderr` output that a "dry run" is taking place.

    Prefixes each line with ``DRY RUN │ `` if *dry_run* is true.

    Does nothing if *dry_run* is not true.

    When entered, returns *dry_run* for the target of the ``with`` statement,
    if any.

    >>> from io import StringIO
    >>> with redirect_stdout(StringIO()) as out, redirect_stderr(out) as stderr:
    ...     with dry_run_indicator(True) as dry_run:
    ...         print("stdout")
    ...         print("stderr", file = sys.stderr)

    >>> print(out.getvalue(), end = "")
    DRY RUN │ stdout
    DRY RUN │ stderr

    >>> dry_run
    True

    >>> with redirect_stdout(StringIO()) as out, redirect_stderr(out) as stderr:
    ...     with dry_run_indicator(False) as dry_run:
    ...         print("stdout")
    ...         print("stderr", file = sys.stderr)

    >>> print(out.getvalue(), end = "")
    stdout
    stderr

    >>> dry_run
    False
    """
    with ExitStack() as stack:
        if dry_run:
            stack.enter_context(redirect_stdout(LinePrefixer(sys.stdout, "DRY RUN │ ")))
            stack.enter_context(redirect_stderr(LinePrefixer(sys.stderr, "DRY RUN │ ")))
        yield dry_run


class LinePrefixer(ObjectProxy): # pyright: ignore[reportUntypedBaseClass]
    """
    Add *prefix* to every line written to *file*.

    >>> import sys
    >>> def output(file):
    ...     print("Swizzling the sporks…", file = file)
    ...     print("Reticulating splines…", file = file, end = "")
    ...     print("\\n  done!", file = file)
    ...     print("Gimbling the wabe (this may take a while)\\n\\n\\n", file = file)
    ...     print("Gyre away!", file = file)

    >>> output(sys.stdout)
    Swizzling the sporks…
    Reticulating splines…
      done!
    Gimbling the wabe (this may take a while)
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    Gyre away!

    >>> output(LinePrefixer(sys.stdout, "DRY RUN: "))
    DRY RUN: Swizzling the sporks…
    DRY RUN: Reticulating splines…
    DRY RUN:   done!
    DRY RUN: Gimbling the wabe (this may take a while)
    DRY RUN: 
    DRY RUN: 
    DRY RUN: 
    DRY RUN: Gyre away!

    Attributes of *file* are passed through the :py:cls:`LinePrefixer` object:

    >>> p = LinePrefixer(sys.__stdout__, "  ")
    >>> p.fileno()
    1
    """
    # Declaring these here keeps them local to this proxy object instead of
    # being written through to the wrapped file object.
    __prefix: str = ""
    __next_write_needs_prefix: bool = True

    def __init__(self, file: TextIO, prefix: str):
        super().__init__(file)
        self.__prefix = prefix
        self.__next_write_needs_prefix = True

    def write(self, s) -> int:
        s_ = ""

        if self.__next_write_needs_prefix:
            s_ += self.__prefix

        # Wait to write a prefix after a trailing newline until the next call.
        # This avoids a dangling prefix if we're never called again.
        self.__next_write_needs_prefix = s.endswith("\n")

        # Insert prefix after every newline except for an end-of-string
        # newline, which we'll account for as above on the next, if any, call
        # to us.
        s_ += re.sub(r'(?<=\n)(?!\Z)', self.__prefix, s)

        return self.__wrapped__.write(s_)

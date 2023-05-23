"""
Debug flags and utilities.

.. envvar:: NEXTSTRAIN_DEBUG

    Set to a truthy value (e.g. 1) to print more information about (handled)
    errors.  For example, when this is not set or falsey, stack traces and
    parent exceptions in an exception chain are omitted from handled errors.
"""
from os import environ
from sys import stderr

DEBUGGING = bool(environ.get("NEXTSTRAIN_DEBUG"))

if DEBUGGING:
    def debug(*args):
        print("DEBUG:", *args, file = stderr)
else:
    def debug(*args):
        pass

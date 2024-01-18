"""
Web browser interaction.

.. envvar:: BROWSER

    A ``PATH``-like list of web browsers to try in preference order, before
    falling back to a set of default browsers.  May be program names, e.g.
    ``firefox``, or absolute paths to specific executables, e.g.
    ``/usr/bin/firefox``.

.. envvar:: NOBROWSER

    If set to a truthy value (e.g. 1) then no web browser will be considered
    available.  This can be useful to prevent opening of a browser when there
    are not other means of doing so.
"""
import webbrowser
from threading import Thread, ThreadError
from os import environ
from typing import Union
from .url import URL
from .util import warn


if environ.get("NOBROWSER"):
    BROWSER = None
else:
    # Avoid text-mode browsers
    TERM = environ.pop("TERM", None)
    try:
        BROWSER = webbrowser.get()
    except:
        BROWSER = None
    finally:
        if TERM is not None:
            environ["TERM"] = TERM


def open_browser(url: Union[str, URL], new_thread: bool = True):
    """
    Opens *url* in a web browser.

    Opens in a new tab, if possible, and raises the window to the top, if
    possible.

    Launches the browser from a separate thread by default so waiting on the
    browser child process doesn't block the main (or calling) thread.  Set
    *new_thread* to False to launch from the same thread as the caller (e.g. if
    you've already spawned a dedicated thread or process for the browser).
    Note that some registered browsers launch in the background themselves, but
    not all do, so this feature makes launch behaviour consistent across
    browsers.

    Prints a warning to stderr if a browser can't be found or can't be
    launched, as automatically opening a browser is considered a
    nice-but-not-necessary feature.
    """
    if not BROWSER:
        warn(f"Couldn't open <{url}> in browser: no browser found")
        return

    try:
        if new_thread:
            Thread(target = open_browser, args = (str(url), False), daemon = True).start()
        else:
            # new = 2 means new tab, if possible
            BROWSER.open(str(url), new = 2, autoraise = True)
    except (ThreadError, webbrowser.Error) as err:
        warn(f"Couldn't open <{url}> in browser: {err!r}")

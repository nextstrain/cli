"""
Visualizes a completed pathogen builds or narratives in Auspice, the Nextstrain
visualization app.

<path> may be a `dataset (.json) file`_ or `narrative (.md) file`_ to start
Auspice and directly open the specified dataset or narrative in a browser.
Adjacent datasets and/or narratives may also be viewable as an appropriate data
directory for Auspice is automatically inferred from the file path.

<path> may also be a directory with one of the following layouts::

    <path>/
    ├── auspice/
    │   └── *.json
    └── narratives/
        └── *.md

    <path>/
    ├── auspice/
    │   └── *.json
    └── *.md

    <path>/
    ├── *.json
    └── narratives/
        └── *.md

    <path>/
    ├── *.json
    └── *.md

Dataset and narrative files will be served, respectively, from **auspice**
and/or **narratives** subdirectories under the given <path> if the
subdirectories exist.  Otherwise, files will be served from the given directory
<path> itself.

If your pathogen build directory follows our conventional layout by containing
an **auspice** directory (and optionally a **narratives** directory), then you
can give ``nextstrain view`` the same path as you do ``nextstrain build``.

Note that by convention files named **README.md** or **group-overview.md** will
be ignored for the purposes of finding available narratives.

.. _dataset (.json) file: https://docs.nextstrain.org/page/reference/glossary.html#term-dataset
.. _narrative (.md) file: https://docs.nextstrain.org/page/reference/glossary.html#term-narrative
"""

from multiprocessing import Process, ProcessError
import re
import webbrowser
from os import environ
from pathlib import Path
from socket import getaddrinfo, AddressFamily, SocketKind, AF_INET, AF_INET6, IPPROTO_TCP
from time import sleep
from typing import Iterable, NamedTuple, Tuple, Union
from .. import runner
from ..argparse import add_extended_help_flags, SUPPRESS, SKIP_AUTO_DEFAULT_IN_HELP
from ..runner import docker, ambient, conda, singularity
from ..util import colored, remove_suffix, warn
from ..volume import NamedVolume


# Avoid text-mode browsers
TERM = environ.pop("TERM", None)
try:
    BROWSER = webbrowser.get()
except:
    BROWSER = None
finally:
    if TERM is not None:
        environ["TERM"] = TERM

OPEN_DEFAULT = bool(BROWSER)


def register_parser(subparser):
    """
    %(prog)s [options] <path>
    %(prog)s --help
    """

    parser = subparser.add_parser("view", help = "View pathogen builds and narratives", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    parser.add_argument(
        "--open",
        help    = "Open a web browser automatically " +
                  ('(the default)' if OPEN_DEFAULT else '') +
                  SKIP_AUTO_DEFAULT_IN_HELP,
        action  = "store_true",
        default = OPEN_DEFAULT)

    parser.add_argument(
        "--no-open",
        dest    = "open",
        help    = "Do not open a web browser automatically " +
                  ('' if OPEN_DEFAULT else '(the default)') +
                  SKIP_AUTO_DEFAULT_IN_HELP,
        action  = "store_false")

    parser.add_argument(
        "--allow-remote-access",
        help   = "Allow other computers on the network to access the website (alias for --host=0.0.0.0)",
        dest   = "host",
        action = "store_const",
        const  = "0.0.0.0",
        default = SUPPRESS)

    parser.add_argument(
        "--host",
        help    = "Listen on the given hostname or IP address instead of the default %(default)s",
        metavar = "<ip/hostname>",
        default = "127.0.0.1")

    parser.add_argument(
        "--port",
        help    = "Listen on the given port instead of the default port %(default)s",
        metavar = "<number>",
        default = 4000)

    # Positional parameters
    parser.add_argument(
        "path",
        help    = "Path to a directory containing dataset JSON and/or narrative Markdown files for Auspice, "
                  "or a directory containing an auspice/ and/or narratives/ directory, "
                  "or a specific dataset JSON or narrative Markdown file.",
        metavar = "<path>",
        type = Path)

    # Register runners; excludes AWS Batch since that makes no sense.
    #
    # Note that the --datasetDir and --narrativeDir here might be overriden in
    # run() below.
    runner.register_runners(
        parser,
        exec    = ["auspice", "view", "--verbose", "--datasetDir=.", "--narrativeDir=."],
        runners = [docker, ambient, conda, singularity])

    return parser


def run(opts):
    data_dir = None
    default_path = None

    if opts.path.is_dir():
        data_dir = opts.path

    elif opts.path.is_file():
        resource_paths = dataset_paths([opts.path]) \
                      or narrative_paths([opts.path])

        if resource_paths:
            default_path = next(iter(resource_paths), None)
            data_dir = opts.path.resolve(strict = False).parent

            # Go up one more level (to X) when we're given a path to
            # …/X/narratives/*.md, in the hopes that the datasets needed by the
            # narrative will be in …/X/ or …/X/auspice/.
            #
            # We don't check if data_dir.name == "auspice" because while
            # narratives rely on datasets, datasets do not rely on narratives.
            if data_dir.name == "narratives":
                data_dir = data_dir.parent

    if not data_dir:
        warn("Error: Path \"%s\" does not exist, or is not a directory, or is not a dataset or narrative file." % opts.path)

        if not opts.path.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    # A volume which will be our working dir.
    working_volume = NamedVolume("auspice/data", data_dir)
    opts.volumes.append(working_volume) # for Docker and Singularity

    # If auspice/ exists, then use it for datasets.  Otherwise, look for
    # datasets in the given dir.
    if (data_dir / "auspice/").is_dir():
        datasets_dir = data_dir / "auspice/"

        # Override our default --datasetDir=. above
        opts.default_exec_args += ["--datasetDir=auspice/"]
    else:
        datasets_dir = data_dir

    # If narratives/ exist, then use it for narratives.  Otherwise, look for
    # narratives in the given dir.
    if (data_dir / "narratives/").is_dir():
        narratives_dir = data_dir / "narratives/"

        # Override our default --narrativeDir=. above
        opts.default_exec_args += ["--narrativeDir=narratives/"]
    else:
        narratives_dir = data_dir

    # Find the available dataset and narrative paths
    datasets = dataset_paths(datasets_dir.glob("*.json"))
    narratives = narrative_paths(narratives_dir.glob("*.md"))

    available_paths = [
        *sorted(datasets, key = str.casefold),
        *sorted(narratives, key = str.casefold),
    ]

    if not default_path and len(available_paths) == 1:
        default_path = available_paths[0]

    # Setup the published port.  Default to localhost for security reasons
    # unless explicitly told otherwise.
    #
    # The environment variables HOST and PORT are respected by auspice's
    # cli/view.js.  HOST requires a new enough version of Auspice; 1.35.7 and
    # earlier always listen on 0.0.0.0 or ::.
    host, port = resolve(opts.host, opts.port)

    env = {
        'HOST': host,
        'PORT': str(port)
    }

    # These are docker-specific details which will only be used when the
    # docker runner (--docker flag) is in use.
    opts.docker_args = [
        *opts.docker_args,

        # auspice's cli (probably thanks to Express or Node?) when run in the
        # circumstances of the container seems to ignore signals (like SIGINT,
        # ^C, or SIGTERM), so run it under an init process that does respect
        # signals.
        "--init",

        # Inside the container, always bind to all interfaces.  This is
        # required for Docker to forward a port from the container's host into
        # the container because of how it does port publishing.  Note that
        # container ports aren't automatically published outside the container,
        # so this still doesn't allow arbitrary access from the outside world.
        # The published port on the container's host is still bound to
        # 127.0.0.1 by default.
        "--env=HOST=0.0.0.0",

        # Publish the port
        "--publish=[%s]:%d:%d" % (host, port, port),
    ]

    # XXX TODO: Find the best remote address if we're allowing remote access.
    # While we listen on all interfaces (0.0.0.0), only the local host can
    # connect to that successfully.  Remote hosts need a real IP on the
    # network, which we do our best to discover.  If something goes wrong,
    # ignore it and leave the host IP as-is (0.0.0.0); it'll at least work for
    # local access.
    #
    # We used to use (in versions <= 3.0.4) the netifaces package to determine
    # this, but netifaces became unmaintained and thus stopped having wheels
    # built for newer Python versions.  This caused installation issues on a
    # myriad of platforms since without wheels a full C toolchain is needed to
    # install it.  For more context, see discussion starting with this comment:
    #
    #   <https://github.com/nextstrain/cli/issues/31#issuecomment-966609539>
    #
    # This comment exists as a reminder that spitting out http://0.0.0.0:4000
    # is not very helpful and we should do better in the future if we
    # reasonably can (e.g. use mDNS/Zeroconf to make nextstrain.your-computer.local
    # Just Work, or even check if netifaces gets revived).
    #   -trs, 17 Dec 2021

    # Show a helpful message about where to connect
    print_url(host, port, available_paths)

    if opts.open:
        open_browser(f"http://{host}:{port}/{default_path or ''}")

    return runner.run(opts, working_volume = working_volume, extra_env = env)


def dataset_paths(paths: Iterable[Path]) -> Iterable[str]:
    """
    Returns a :py:class:`set` of Auspice (not filesystem) paths for datasets in
    *paths*.
    """
    # This file matching/organization logic is similar to organize_files() in
    # nextstrain/cli/remote/nextstrain_dot_org.py, but with a slightly
    # different use case.  I considered combining the two, but ultimately
    # deemed it better to just keep them separate for now.
    #
    # Note also that here "sidecar" is used to describe suffixes which include
    # Augur "node data" files, though those aren't true dataset sidecars.  The
    # list below also doesn't include all such known suffixes; see
    # <https://docs.nextstrain.org/en/latest/reference/data-formats.html> for
    # more examples.
    #   -trs, 11 Jan 2022

    # v2: All *.json files which don't end with a known sidecar or v1 suffix.
    sidecar_suffixes = {"meta", "tree", "root-sequence", "seq", "sequences", "tip-frequencies", "measurements", "entropy"}

    def sidecar_file(path):
        return any(path.name.endswith("_%s.json" % suffix) for suffix in sidecar_suffixes)

    datasets_v2 = set(
        path.stem.replace("_", "/")
            for path in paths
            if path.match("*.json") and not sidecar_file(path))

    # v1: All *_tree.json files with corresponding *_meta.json files.
    def meta_exists(path):
        return path.with_name(remove_suffix("_tree.json", path.name) + "_meta.json").exists()

    datasets_v1 = set(
        re.sub(r"_tree$", "", path.stem).replace("_", "/")
            for path in paths
            if path.match("*_tree.json") and meta_exists(path))

    return datasets_v2 | datasets_v1


def narrative_paths(paths: Iterable[Path]) -> Iterable[str]:
    """
    Returns a :py:class:`set` of Auspice (not filesystem) paths for narratives
    in *paths*.
    """
    # Narratives: all *.md files except README.md and group-overview.md
    return {
        "narratives/" + path.stem.replace("_", "/")
            for path in paths
             if path.match("*.md")
            and path.name not in {"README.md", "group-overview.md"}}


def print_url(host, port, available_paths):
    """
    Prints a list of available dataset and narrative URLs, if any.  Otherwise,
    prints a generic URL.
    """
    # Surround IPv6 addresses with square brackets for the URL.
    if ":" in host:
        host = f"[{host}]"

    def url(path = None):
        return colored(
            "blue",
            "http://{host}:{port}/{path}".format(
                host = host,
                port = port,
                path = path if path is not None else ""))

    horizontal_rule = colored("green", "—" * 78)

    print()
    print(horizontal_rule)

    if available_paths:
        print("    The following datasets and/or narratives should be available in a moment:")
        for path in available_paths:
            print("       • %s" % url(path))
    else:
        print("    Open <%s> in your browser." % url())
        print()
        print("   ", colored("yellow", "Warning: No datasets or narratives detected."))

    print(horizontal_rule)
    print()


def resolve(host, port) -> Tuple[str, int]:
    """
    Resolves *host* to an address and *port* to a number, if either is a name.

    Returns a tuple of (ip, port) if possible; otherwise returns (host, port)
    as given (which may work, but will probably fail).

    IPv4 addresses are preferred, but IPv6 addresses be returned if no IPv4
    addresses are available.
    """
    addrs = [AddressInfo(*a) for a in getaddrinfo(host, port, proto = IPPROTO_TCP)]

    ip4 = [a for a in addrs if a.family is AF_INET]
    ip6 = [a for a in addrs if a.family is AF_INET6]

    return ip4[0].sockaddr[0:2] if ip4 \
      else ip6[0].sockaddr[0:2] if ip6 \
      else (host, int(port))


class AddressInfo(NamedTuple):
    family: AddressFamily
    type: SocketKind
    proto: int
    canonname: str
    sockaddr: Union[Tuple[str, int], Tuple[str, int, int, int]] # (ip, addr, ...)


def open_browser(url: str) -> bool:
    try:
        Process(target = _open_browser, args = (url,), daemon = True).start()
        return True
    except ProcessError as err:
        warn(f"Couldn't open <{url}> in browser: {err!r}")
        return False


# This function runs in a separate process.  The process is started via
# different methods (either forking or spawning) depending on the platform, per
# multiprocessing defaults (and, in our standalone executable, PyOxidizer
# defaults).  As the start method impacts what state (e.g. variables, fds, etc)
# is shared between the processes, this function needs to accomodate the method
# with the least shared state (i.e. "spawn").  Otherwise, it may work fine
# under the "fork" start method but not under "spawn", and this may not be
# noticeable during development.  Our tests in tests/open_browser.py try to
# ensure we don't mess it up.
#   -trs, 21 Dec 2022
def _open_browser(url: str):
    if not BROWSER:
        warn(f"Couldn't open <{url}> in browser: no browser found")
        return

    # XXX TODO: Many better ways to wait for Auspice to be running… but this is
    # the simplest (if not the most reliable or most responsive).
    #   -trs, 6 Dec 2022
    sleep(2)

    try:
        # new = 2 means new tab, if possible
        BROWSER.open(url, new = 2, autoraise = True)
    except webbrowser.Error as err:
        warn(f"Couldn't open <{url}> in browser: {err!r}")

"""
Visualizes a completed pathogen build in auspice, the Nextstrain web frontend.

The data directory should contain sets of files with at least two files:

    <prefix>_tree.json
    <prefix>_meta.json

The viewer runs inside a container, which requires Docker.  See `nextstrain
build --help` for more information on the setup and use of Docker.
"""

import re
from pathlib import Path
from ..runner import docker


def register_parser(subparser):
    parser = subparser.add_parser("view", help = "View pathogen build")
    parser.description = __doc__

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build data directory",
        metavar = "<directory>",
        action  = docker.store_volume("auspice/data"))

    # Runner options
    docker.register_arguments(
        parser,
        exec    = ["auspice"],
        volumes = ["auspice"])

    return parser


def run(opts):
    # Try to find the available dataset paths since we may not have a manifest
    data_dir = Path(opts.auspice_data.src)
    datasets = [
        re.sub(r"_tree$", "", path.stem).replace("_", "/")
            for path in data_dir.glob("*_tree.json")
    ]

    # Setup the published port.
    #
    # There are docker-specific implementation details here that should be
    # refactored once we have more than one nextstrain.cli.runner module in
    # play.  Doing that work now would be premature; we'll get a better
    # interface for ports/environment when we have concrete requirements.
    #   -trs, 27 June 2018
    port = 4000

    if opts.docker_args is None:
        opts.docker_args = []

    opts.docker_args = [
        *opts.docker_args,

        # PORT is respected by auspice's server.js
        "--env=PORT=%d" % port,

        # Publish the port only to the localhost
        "--publish=127.0.0.1:%d:%d" % (port, port),
    ]

    # Show a helpful message about where to connect
    print_url("localhost", port, datasets)

    return docker.run(opts)


def print_url(host, port, datasets):
    """
    Prints a list of available dataset URLs, if any.  Otherwise, prints a
    generic URL.
    """

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

    if len(datasets):
        print("    The following datasets should be available in a moment:")
        for path in sorted(datasets, key = str.casefold):
            print("       • %s" % url(path))
    else:
        print("    Open <%s> in your browser." % url())

    print(horizontal_rule)


def colored(color, text):
    """
    Returns a string of text suitable for colored output on a terminal.
    """

    # These magic numbers are standard ANSI terminal escape codes for
    # formatting text.
    colors = {
        "green": "\033[0;32m",
        "blue":  "\033[0;1;34m",
        "reset": "\033[0m",
    }

    return "{start}{text}{end}".format(
        start = colors[color],
        end   = colors["reset"],
        text  = text,
    )

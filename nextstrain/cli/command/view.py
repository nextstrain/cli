"""
Visualizes a completed pathogen build in auspice, the Nextstrain web frontend.

The data directory should contain sets of files with at least two files:

    <prefix>_tree.json
    <prefix>_meta.json

The viewer runs inside a container, which requires Docker.  Run `nextstrain
check-setup` to check if Docker is installed and works.
"""

import re
import netifaces as net
from .. import runner
from ..argparse import add_extended_help_flags
from ..runner import docker
from ..util import colored, warn
from ..volume import store_volume


def register_parser(subparser):
    """
    %(prog)s [options] <directory>
    %(prog)s --help
    """

    parser = subparser.add_parser("view", help = "View pathogen build", add_help = False)

    # Support --help and --help-all
    add_extended_help_flags(parser)

    parser.add_argument(
        "--allow-remote-access",
        help   = "Allow other computers on the network to access the website",
        action = "store_true")

    # Positional parameters
    parser.add_argument(
        "directory",
        help    = "Path to pathogen build data directory",
        metavar = "<directory>",
        action  = store_volume("auspice/data"))

    # Register runners; only Docker is supported for now since auspice doesn't
    # have a native wrapper command yet.
    runner.register_runners(
        parser,
        exec    = ["auspice"],
        runners = [docker])

    return parser


def run(opts):
    # Ensure our data path is a directory that exists
    data_dir = opts.auspice_data.src

    if not data_dir.is_dir():
        warn("Error: Data path \"%s\" does not exist or is not a directory." % data_dir)

        if not data_dir.is_absolute():
            warn()
            warn("Perhaps your current working directory is different than you expect?")

        return 1

    # Try to find the available dataset paths since we may not have a manifest
    datasets = [
        re.sub(r"_tree$", "", path.stem).replace("_", "/")
            for path in data_dir.glob("*_tree.json")
    ]

    # Setup the published port.  Default to localhost for security reasons
    # unless explicitly told otherwise.
    #
    # There are docker-specific implementation details here that should be
    # refactored once we have more than one nextstrain.cli.runner module in
    # play.  Doing that work now would be premature; we'll get a better
    # interface for ports/environment when we have concrete requirements.
    #   -trs, 27 June 2018
    host = "0.0.0.0" if opts.allow_remote_access else "127.0.0.1"
    port = 4000

    opts.docker_args = [
        *opts.docker_args,

        # PORT is respected by auspice's server.js
        "--env=PORT=%d" % port,

        # Publish the port
        "--publish=%s:%d:%d" % (host, port, port),
    ]

    # Find the best remote address if we're allowing remote access.  While we
    # listen on all interfaces (0.0.0.0), only the local host can connect to
    # that successfully.  Remote hosts need a real IP on the network, which we
    # do our best to discover.  If something goes wrong, ignore it and leave
    # the host IP as-is (0.0.0.0); it'll at least work for local access.
    if opts.allow_remote_access:
        try:
            remote_address = best_remote_address()
        except:
            pass
        else:
            host = remote_address

    # Show a helpful message about where to connect
    print_url(host, port, datasets)

    return runner.run(opts, working_volume = opts.auspice_data)


def print_url(host, port, datasets):
    """
    Prints a list of available dataset URLs, if any.  Otherwise, prints a
    generic URL.
    """

    def url(path = None):
        return colored(
            "blue",
            "http://{host}:{port}/local/{path}".format(
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
        print()
        print("   ", colored("yellow", "Warning: No datasets detected."))

    print(horizontal_rule)
    print()


def best_remote_address():
    """
    Returns the "best" non-localback IP address for the local host, if
    possible.  The "best" IP address is that bound to either the default
    gateway interface, if any, else the arbitrary first interface found.

    IPv4 is preferred, but IPv6 will be used if no IPv4 interfaces/addresses
    are available.
    """
    default_gateway   = net.gateways().get("default", {})
    default_interface = default_gateway.get(net.AF_INET,  (None, None))[1] \
                     or default_gateway.get(net.AF_INET6, (None, None))[1] \
                     or net.interfaces()[0]

    interface_addresses = net.ifaddresses(default_interface).get(net.AF_INET)  \
                       or net.ifaddresses(default_interface).get(net.AF_INET6) \
                       or []

    addresses = [
        address["addr"]
            for address in interface_addresses
             if address.get("addr")
    ]

    return addresses[0] if addresses else None

"""
List datasets and narratives on a remote source.
 
A remote source URL specifies what to list, e.g. to list what's in the
Nextstrain Group named "Blab"::

    nextstrain remote list nextstrain.org/groups/blab

or list the core seasonal influenza datasets::

    nextstrain remote list nextstrain.org/flu/seasonal

See `nextstrain remote --help` for more information on remote sources.
"""

from ...remote import parse_remote_path


def register_parser(subparser):
    """
    %(prog)s <remote-url>
    %(prog)s --help
    """
    parser = subparser.add_parser(
        "list",
        aliases = ["ls"],
        help    = "List datasets and narratives")

    parser.add_argument(
        "remote_path",
        help    = "Remote source URL, with optional path prefix to scope/filter the results",
        metavar = "<remote-url>")

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote_path)

    files = remote.ls(url)

    for file in files:
        print(file)

    return 0

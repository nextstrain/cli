"""
Delete pathogen JSON data files or Markdown narratives from a remote source.

See `nextstrain remote --help` for more information on remote sources.
"""

from ...remote import parse_remote_path
from ...util import warn


def register_parser(subparser):
    parser = subparser.add_parser(
        "delete",
        aliases = ["rm"],
        help    = "Delete dataset and narrative files")

    parser.add_argument(
        "remote_path",
        help    = "Remote path as a URL",
        metavar = "<s3://bucket-name>")

    parser.add_argument(
        "--recursively", "-r",
        help   = "Delete files recursively under the given path prefix",
        action = "store_true")

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote_path)

    deleted = remote.delete(url, recursively = opts.recursively)
    deleted_count = 0

    for file in deleted:
        print("deleted: %s" % file)
        deleted_count += 1

    if deleted_count:
        return 0
    else:
        warn("Nothing deleted!")
        return 1

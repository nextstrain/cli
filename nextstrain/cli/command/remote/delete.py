"""
Delete datasets and narratives on a remote source.

A remote source URL specifies what to delete, e.g. to delete the "beta-cov"
dataset in the Nextstrain Group "blab"::

    nextstrain remote delete nextstrain.org/groups/blab/beta-cov

The --recursively option allows for deleting multiple datasets or narratives
at once, e.g. to delete all the "ncov/wa/…" datasets in the "blab" group::

    nextstrain remote delete --recursively nextstrain.org/groups/blab/ncov/wa

See `nextstrain remote --help` for more information on remote sources.
"""

from ... import console
from ...remote import parse_remote_path
from ...util import warn


def register_parser(subparser):
    """
    %(prog)s [--recursively] <remote-url>
    %(prog)s --help
    """
    parser = subparser.add_parser(
        "delete",
        aliases = ["rm"],
        help    = "Delete dataset and narratives")

    parser.add_argument(
        "remote_path",
        help    = "Remote source URL for a dataset or narrative.  "
                  "A path prefix to scope/filter by if using --recursively.",
        metavar = "<remote-url>")

    parser.add_argument(
        "--recursively", "-r",
        help   = "Delete everything under the given remote URL path prefix",
        action = "store_true")

    parser.add_argument(
        "--dry-run",
        help   = "Don't actually delete anything, just show what would be deleted",
        action = "store_true")

    return parser


@console.auto_dry_run_indicator()
def run(opts):
    remote, url = parse_remote_path(opts.remote_path)

    deletions = remote.delete(url, recursively = opts.recursively, dry_run = opts.dry_run)
    deleted_count = 0

    for file in deletions:
        print("Deleting", file)
        deleted_count += 1

    if deleted_count:
        return 0
    else:
        warn("Nothing deleted!")
        return 1

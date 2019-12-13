"""
Delete pathogen JSON data files or Markdown narratives from a remote source.

See `nextstrain remote --help` for more information on remote sources.
"""

from urllib.parse import urlparse
from ...remote import s3
from ...util import warn


SUPPORTED_SCHEMES = {
    "s3": s3,
}


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
    url = urlparse(opts.remote_path)

    if url.scheme not in SUPPORTED_SCHEMES:
        warn("Error: Unsupported remote scheme %s://" % url.scheme)
        warn("")
        warn("Supported schemes are: %s" % ", ".join(SUPPORTED_SCHEMES))
        return 1

    remote = SUPPORTED_SCHEMES[url.scheme]

    deleted, errors = remote.delete(url, recursively = opts.recursively)

    for file in deleted:
        print("deleted: %s" % file)

    for file, *details in errors:
        warn('failed to delete "%s": %s' % (file, details))

    if not deleted:
        warn("Nothing deleted!")

    return 0 if deleted and not errors else 1

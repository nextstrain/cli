"""
List pathogen JSON data files or Markdown narratives on a remote source.
 
URLs support optional path prefixes for restricting the files listed.

    nextstrain remote list s3://my-bucket/some/prefix/

will list files named "some/prefix/*".

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
        "list",
        aliases = ["ls"],
        help    = "List dataset and narrative files")

    parser.add_argument(
        "remote_path",
        help    = "Remote path as a URL, with optional key/path prefix",
        metavar = "<s3://bucket-name>")

    return parser


def run(opts):
    url = urlparse(opts.remote_path)

    if url.scheme not in SUPPORTED_SCHEMES:
        warn("Error: Unsupported remote scheme %s://" % url.scheme)
        warn("")
        warn("Supported schemes are: %s" % ", ".join(SUPPORTED_SCHEMES))
        return 1

    remote = SUPPORTED_SCHEMES[url.scheme]

    files = remote.ls(url)

    for file in files:
        print(file)

    return 0

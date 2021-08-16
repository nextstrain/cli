"""
List pathogen JSON data files or Markdown narratives on a remote source.
 
URLs support optional path prefixes for restricting the files listed.

    nextstrain remote list s3://my-bucket/some/prefix/

will list files named `some/prefix/*`.

See `nextstrain remote --help` for more information on remote sources.
"""

from ...remote import parse_remote_path


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
    remote, url = parse_remote_path(opts.remote_path)

    files = remote.ls(url)

    for file in files:
        print(file)

    return 0

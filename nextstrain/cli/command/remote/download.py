"""
Downloads pathogen JSON data files or Markdown narratives from a remote
source.
 
Source URLs specify the file(s) to download:

    nextstrain remote download s3://my-bucket/some/prefix/data.json

will download "data.json" into the current directory.

Recursive downloads are supported for downloading multiple files:

    nextstrain remote download --recursive s3://my-bucket/some/prefix/

will download all files under "some/prefix/" into the current directory.

See `nextstrain remote --help` for more information on remote sources.
"""

from pathlib import Path
from ...remote import parse_remote_path
from ...util import warn


def register_parser(subparser):
    parser = subparser.add_parser("download", help = "Download dataset and narrative files")

    parser.add_argument(
        "remote_path",
        help    = "Remote file path as a URL",
        metavar = "<s3://bucket-name>")

    parser.add_argument(
        "local_path",
        help    = "Local directory to save files in.  "
                  "May be a local filename to use if the remote path points to a single file.",
        metavar = "<path>",
        type    = Path,
        nargs   = "?",
        default = ".")

    parser.add_argument(
        "--recursively", "-r",
        help   = "Download all files with the given remote path prefix",
        action = "store_true")

    return parser


def run(opts):
    remote, url = parse_remote_path(opts.remote_path)

    if opts.recursively and not opts.local_path.is_dir():
        warn("Local path must be a directory when using --recursively; «%s» is not" % opts.local_path)
        return 1

    downloads = remote.download(url, opts.local_path, recursively = opts.recursively)

    for remote_file, local_file in downloads:
        print("Downloading", remote_file, "as", local_file)

    return 0

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
from urllib.parse import urlparse
from ...remote import s3
from ...util import warn


SUPPORTED_SCHEMES = {
    "s3": s3,
}


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
    url = urlparse(opts.remote_path)

    if url.scheme not in SUPPORTED_SCHEMES:
        warn("Error: Unsupported remote scheme %s://" % url.scheme)
        warn("")
        warn("Supported schemes are: %s" % ", ".join(SUPPORTED_SCHEMES))
        return 1

    remote = SUPPORTED_SCHEMES[url.scheme]

    if opts.recursively and not opts.local_path.is_dir():
        warn("Local path must be a directory when using --recursively; «%s» is not" % opts.local_path)
        return 1

    downloads = remote.download(url, opts.local_path, recursively = opts.recursively)

    for remote_file, local_file in downloads:
        print("Downloading", remote_file, "as", local_file)

    return 0

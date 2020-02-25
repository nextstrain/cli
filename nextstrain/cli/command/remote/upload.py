"""
Uploads (deploys) a set of built pathogen JSON data files or Markdown
narratives to a remote source.

Source URLs support optional path prefixes if you want your local filenames to
be prefixed on the remote.  For example:

    nextstrain remote upload s3://my-bucket/some/prefix/ auspice/zika*.json

will upload files named "some/prefix/zika*.json".

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
    parser = subparser.add_parser("upload", help = "Upload dataset and narrative files")

    register_arguments(parser)
    
    return parser


def register_arguments(parser):
    # Destination
    parser.add_argument(
        "destination",
        help    = "Remote path as a URL, with optional key/path prefix",
        metavar = "<s3://bucket-name>")

    # Files to upload
    parser.add_argument(
        "files",
        help    = "Files to upload, typically Auspice JSON data files",
        metavar = "<file.json>",
        nargs   = "+")


def run(opts):
    url = urlparse(opts.destination)

    if url.scheme not in SUPPORTED_SCHEMES:
        warn("Error: Unsupported destination scheme %s://" % url.scheme)
        warn("")
        warn("Supported schemes are: %s" % ", ".join(SUPPORTED_SCHEMES))
        return 1

    remote = SUPPORTED_SCHEMES[url.scheme]
    files  = [Path(f) for f in opts.files]

    uploads = remote.upload(url, files)

    for local_file, remote_file in uploads:
        print("Uploading", local_file, "as", remote_file)

    return 0

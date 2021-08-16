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
from ...remote import parse_remote_path


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
    remote, url = parse_remote_path(opts.destination)

    files = [Path(f) for f in opts.files]

    uploads = remote.upload(url, files)

    for local_file, remote_file in uploads:
        print("Uploading", local_file, "as", remote_file)

    return 0

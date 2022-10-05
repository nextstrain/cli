"""
Upload dataset and narratives files to a remote destination.

A remote destination URL specifies where to upload, e.g. to upload the dataset
files::

    auspice/ncov_local.json
    auspice/ncov_local_root-sequence.json
    auspice/ncov_local_tip-frequencies.json

so they're visible at `https://nextstrain.org/groups/example/ncov`::

    nextstrain remote upload nextstrain.org/groups/example/ncov auspice/ncov_local*.json

If uploading multiple datasets or narratives, uploading to the top-level of a
Nextstrain Group, or uploading to an S3 remote, then the local filenames are
used in combination with any path prefix in the remote source URL.

See `nextstrain remote --help` for more information on remote sources.
"""

from pathlib import Path
from ... import console
from ...remote import parse_remote_path


def register_parser(subparser):
    """
    %(prog)s <remote-url> <file> [<file2> […]]
    %(prog)s --help
    """
    parser = subparser.add_parser("upload", help = "Upload dataset and narrative files")

    register_arguments(parser)
    
    return parser


def register_arguments(parser):
    # Destination
    parser.add_argument(
        "destination",
        help    = "Remote destination URL for a dataset or narrative.  "
                  "A path prefix if the files to upload comprise more than "
                  "one dataset or narrative or the remote is S3.",
        metavar = "<remote-url>")

    # Files to upload
    parser.add_argument(
        "files",
        help    = "Files to upload.  "
                  "Typically dataset and sidecar files (Auspice JSON files) "
                  "and/or narrative files (Markdown files).",
        metavar = "<file> [<file2> […]]",
        nargs   = "+")

    parser.add_argument(
        "--dry-run",
        help   = "Don't actually upload anything, just show what would be uploaded",
        action = "store_true")


@console.auto_dry_run_indicator()
def run(opts):
    remote, url = parse_remote_path(opts.destination)

    files = [Path(f) for f in opts.files]

    uploads = remote.upload(url, files, dry_run = opts.dry_run)

    for local_file, remote_file in uploads:
        print("Uploading", local_file, "as", remote_file)

    return 0

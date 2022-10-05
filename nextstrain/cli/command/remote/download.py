"""
Download datasets and narratives from a remote source.
 
A remote source URL specifies what to download, e.g. to download one of the
seasonal influenza datasets::

    nextstrain remote download nextstrain.org/flu/seasonal/h3n2/ha/2y

which creates three files in the current directory::

    flu_seasonal_h3n2_ha_2y.json
    flu_seasonal_h3n2_ha_2y_root-sequence.json
    flu_seasonal_h3n2_ha_2y_tip-frequencies.json

The --recursively option allows for downloading multiple datasets or narratives
at once, e.g. to download all the datasets under "ncov/open/…" into an existing
directory named "sars-cov-2"::

    nextstrain remote download --recursively nextstrain.org/ncov/open sars-cov-2/

which creates files for each dataset::

    sars-cov-2/ncov_open_global.json
    sars-cov-2/ncov_open_global_root-sequence.json
    sars-cov-2/ncov_open_global_tip-frequencies.json
    sars-cov-2/ncov_open_africa.json
    sars-cov-2/ncov_open_africa_root-sequence.json
    sars-cov-2/ncov_open_africa_tip-frequencies.json
    …

See `nextstrain remote --help` for more information on remote sources.
"""

import shlex
from pathlib import Path
from ... import console
from ...remote import parse_remote_path
from ...errors import UserError


def register_parser(subparser):
    """
    %(prog)s <remote-url> [<local-path>]
    %(prog)s --recursively <remote-url> [<local-directory>]
    %(prog)s --help
    """
    parser = subparser.add_parser("download", help = "Download dataset and narrative files")

    parser.add_argument(
        "remote_path",
        help    = "Remote source URL for a dataset or narrative.  "
                  "A path prefix to scope/filter by if using --recursively.",
        metavar = "<remote-url>")

    parser.add_argument(
        "local_path",
        help    = "Local directory to save files in.  "
                  "May be a local filename to use if not using --recursively.  "
                  'Defaults to current directory ("%(default)s").',
        metavar = "<local-path>",
        type    = Path,
        nargs   = "?",
        default = ".")

    parser.add_argument(
        "--recursively", "-r",
        help   = "Download everything under the given remote URL path prefix",
        action = "store_true")

    parser.add_argument(
        "--dry-run",
        help   = "Don't actually download anything, just show what would be downloaded",
        action = "store_true")

    return parser


@console.auto_dry_run_indicator()
def run(opts):
    remote, url = parse_remote_path(opts.remote_path)

    if opts.recursively and not opts.local_path.is_dir():
        if opts.local_path.exists():
            raise UserError(f"Local path must be a directory when using --recursively, but «{opts.local_path}» is not.")
        else:
            raise UserError(f"""
                Local path must be a directory when using --recursively, but «{opts.local_path}» doesn't exist.

                If the name is correct, you must create the directory before downloading, e.g.:

                    mkdir -p {shlex.quote(str(opts.local_path))}
                """)

    downloads = remote.download(url, opts.local_path, recursively = opts.recursively, dry_run = opts.dry_run)

    for remote_file, local_file in downloads:
        print("Downloading", remote_file, "as", local_file)

    return 0

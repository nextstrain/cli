"""
Upload, download, and manage remote datasets and narratives.

nextstrain.org is the primary remote source/destination, but Amazon S3 buckets
are also supported and necessary for some use cases. [#history]_

Remote sources/destinations are specified using URLs starting with
`https://nextstrain.org/` and `s3://<bucket-name>/`.  nextstrain.org remote
URLs represent datasets and narratives each as a whole, where datasets may
consist of multiple files (the main JSON file + optional sidecar files) when
uploading/downloading.  Amazon S3 remote URLs represent dataset and narrative
files individually.

For more details on using each remote, see their respective documentation
pages:

    * :doc:`/remotes/nextstrain.org`
    * :doc:`/remotes/s3`

For more information on dataset (Auspice JSON) and narrative (Markdown) files,
see :doc:`docs:reference/data-formats`.

.. [#history] In previous versions, only Amazon S3 buckets were supported.  The
    introduction of nextstrain.org support largely obsoletes the need to use S3
    directly.  Exceptions include if you need to manage v1 datasets (i.e.  separate
    ``*_tree.json`` and ``*_meta.json`` files) or Nextstrain Group overview/logo
    files (``group-overview.md`` or ``group-logo.png``).
"""

# Guard against __doc__ being None to appease the type checkers.
__shortdoc__ = (__doc__ or "").strip().splitlines()[0]


from . import upload, download, ls, delete


def register_parser(subparser):
    parser = subparser.add_parser("remote", help = __shortdoc__)

    parser.subcommands = [
        upload,
        download,
        ls,
        delete,
    ]

    return parser

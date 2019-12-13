"""
Upload, download, and manage Nextstrain files on remote sources.

Remote sources host the Auspice JSON data files and Markdown narratives that
are fetched by nextstrain.org or standalone instances of Auspice.
 
Currently only Amazon S3 buckets (s3://…) are supported as the remote
source, but others can be added in the future.

Credentials for authentication should generally be provided by environment
variables specific to each source.

Amazon S3
---------

* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY

More information at:

    https://boto3.readthedocs.io/en/latest/guide/configuration.html#environment-variables

A persistent credentials file, ~/.aws/credentials, is also supported:

    https://boto3.readthedocs.io/en/latest/guide/configuration.html#shared-credentials-file
 
"""

__shortdoc__ = __doc__.strip().splitlines()[0]


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

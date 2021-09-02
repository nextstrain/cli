"""
Upload, download, and manage Nextstrain files on remote sources.

Remote sources host the Auspice JSON data files and Markdown narratives that
are fetched by nextstrain.org or standalone instances of Auspice.
 
Currently only Amazon S3 buckets (s3://…) are supported as the remote source,
but others can be added in the future.  Credentials for authentication are
specific for each remote source.

Amazon S3
    The following environment variables can be used to provide credentials:

        * AWS_ACCESS_KEY_ID
        * AWS_SECRET_ACCESS_KEY

    Amazon's documentation includes more information:
    <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#environment-variables>.

    A persistent credentials file, ~/.aws/credentials, is also supported:
    <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#shared-credentials-file>.

"""

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

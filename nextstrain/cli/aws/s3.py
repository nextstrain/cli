"""
S3 handling.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from typing import Tuple

from ..errors import UserError
from ..types import S3Bucket
from ..url import URL


def split_url(url: URL) -> Tuple[S3Bucket, str]:
    """
    Splits the given s3:// *url* into a Bucket object and normalized path
    with some sanity checking.
    """
    if not url.scheme == "s3":
        raise UserError(f"Expected an s3://… URL but got a URL for {url.scheme}:… instead: {str(url)!r}")

    # Require a bucket name
    if not url.netloc:
        raise UserError("No bucket name specified in url (%s)" % url.geturl())

    # Remove leading slashes from any destination path in order to use it as a
    # prefix for uploaded files.  Internal and trailing slashes are untouched.
    prefix = url.path.lstrip("/")

    try:
        bucket = boto3.resource("s3").Bucket(url.netloc)

    except (NoCredentialsError, PartialCredentialsError) as error:
        raise UserError("Unable to authenticate with S3: %s" % error) from error

    # Find the bucket and ensure we have access and that it already exists so
    # we don't automagically create new buckets.
    try:
        boto3.client("s3").head_bucket(Bucket = bucket.name)

    except ClientError:
        raise UserError(f"""
            Unable to read from S3 bucket "{bucket.name}". Possible reasons:

            1. Your AWS credentials are invalid.
            2. Your AWS credentails are valid but lack permissions to the bucket.
            3. The bucket does not exist (buckets are not automatically created for safety reasons).
            """)

    return bucket, prefix

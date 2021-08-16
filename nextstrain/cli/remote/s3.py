"""
S3 remote with automatic CloudFront invalidation.

Backend module for the remote family of commands.
"""

import boto3
import mimetypes
import re
import urllib.parse
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, WaiterError
from operator import methodcaller
from os.path import commonprefix
from pathlib import Path
from time import time
from typing import Iterable, List, Tuple
from .. import aws
from ..gzip import GzipCompressingReader, ContentDecodingWriter
from ..util import warn, remove_prefix
from ..errors import UserError
from ..types import S3Bucket, S3Object


# Add these statically so that they're always available, even if there's no
# system MIME type registry.  These are the most common types of files we
# expect to upload.
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("text/markdown", ".md")


def upload(url: urllib.parse.ParseResult, local_files: List[Path]) -> Iterable[Tuple[Path, Path]]:
    """
    Upload the *local_files* to the bucket and optional prefix specified by *url*.
    """
    bucket, prefix = split_url(url)

    # Create a set of (local name, remote name) tuples.  S3 is a key-value
    # store, not a filesystem, so this remote name prefixing is intentionally a
    # pure string prefix instead of a path-based prefix (which assumes
    # directory structure semantics).
    files = list(zip(local_files, [ prefix + f.name for f in local_files ]))

    for local_file, remote_file in files:
        yield local_file, Path(remote_file)

        # Upload compressed data
        with GzipCompressingReader(local_file.open("rb")) as gzdata:
            bucket.upload_fileobj(
                gzdata,
                remote_file,
                { "ContentType": content_type(local_file), "ContentEncoding": "gzip" })

    # Purge any CloudFront caches for this bucket
    purge_cloudfront(bucket, [remote for local, remote in files])


def download(url: urllib.parse.ParseResult, local_path: Path, recursively: bool = False) -> Iterable[Tuple[Path, Path]]:
    """
    Download the files deployed at the given remote *url*, optionally
    *recursively*, saving them into the *local_dir*.
    """
    bucket, path = split_url(url)

    # Download either all objects sharing a prefix or the sole object (if any)
    # with the given key.
    if recursively:
        objects = [ item.Object() for item in bucket.objects.filter(Prefix = path) ]
    else:
        if not path:
            raise UserError(f"""
                No file path specified in URL ({url.geturl()!s}); nothing to download.

                Did you mean to use --recursively?
                """)

        object = bucket.Object(path)
        assert_exists(object)

        objects = [ object ]

    def local_file_path(obj):
        if local_path.is_dir():
            return local_path / Path(obj.key).name
        else:
            return local_path

    files = list(zip(objects, [local_file_path(obj) for obj in objects]))

    for remote_object, local_file in files:
        yield Path(remote_object.key), local_file

        encoding = remote_object.content_encoding

        with ContentDecodingWriter(encoding, local_file.open("wb")) as file:
            remote_object.download_fileobj(file)


def ls(url: urllib.parse.ParseResult) -> Iterable[Path]:
    """
    List the files deployed at the given remote *url*.
    """
    bucket, prefix = split_url(url)

    return [ Path(obj.key) for obj in bucket.objects.filter(Prefix = prefix) ]


def delete(url: urllib.parse.ParseResult, recursively: bool = False) -> Iterable[Path]:
    """
    Delete the files deployed at the given remote *url*, optionally *recursively*.
    """
    bucket, path = split_url(url)

    # Prevent unintentionally deleting everything recursively.  It also makes
    # sense for non-recursive deletion, since we don't support deleting the
    # bucket itself.
    if not path:
        raise UserError("No path specified for deletion.")

    # Delete either all objects sharing a prefix or the sole object (if any)
    # with the given key.  This doesn't use the bulk-deletion API in order to
    # more easily provide a nicer generator API to our caller.
    if recursively:
        objects = [ item.Object() for item in bucket.objects.filter(Prefix = path) ]
    else:
        object = bucket.Object(path)
        assert_exists(object)

        objects = [ object ]

    for object in objects:
        yield Path(object.key)
        object.delete()

    if objects:
        purge_cloudfront(bucket, [ obj.key for obj in objects ])


def split_url(url: urllib.parse.ParseResult) -> Tuple[S3Bucket, str]:
    """
    Splits the given s3:// *url* into a Bucket object and normalized path
    with some sanity checking.
    """
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

    except ClientError as error:
        raise UserError(f"""
            No bucket exists with the name "{bucket.name}".

            Buckets are not automatically created for safety reasons.
            """)

    return bucket, prefix


def assert_exists(object: S3Object):
    """
    Raise a :py:class:`UserError` if the given S3 *object* does not exist.
    """
    if not exists(object):
        raise UserError("The file s3://%s/%s does not exist." % (object.bucket_name, object.key))


def exists(object: S3Object) -> bool:
    """
    Test if the given S3 *object* exists.

    Returns a boolean.
    """
    try:
        object.load()
        return True
    except ClientError as error:
        if 404 == int(error.response['Error']['Code']):
            return False
        else:
            raise


def content_type(path: Path) -> str:
    """
    Guess the content type of *path* from its name.

    If the type is not guessable, returns the generic type
    ``application/octet-stream``.
    """
    type, encoding = mimetypes.guess_type(path.name)
    return type or "application/octet-stream"


def purge_cloudfront(bucket, paths: List[str]) -> None:
    """
    Invalidate any CloudFront distribution paths which match the given list of
    file paths originating in the given S3 bucket.
    """
    cloudfront = aws.client_with_default_region("cloudfront")

    # Find the common prefix of this fileset, if any.
    prefix = commonprefix(paths)

    # For each CloudFront distribution origin serving from this bucket (with a
    # matching or broader prefix), if any, purge the prefix path.
    for distribution, origin in distribution_origins_for_bucket(cloudfront, bucket.name, prefix):
        purge_prefix(cloudfront, distribution, origin, prefix)


def purge_prefix(cloudfront, distribution: dict, origin: dict, prefix: str) -> None:
    distribution_id     = distribution["Id"]
    distribution_domain = domain_names(distribution)[0]

    # Purge everything starting with the prefix, after removing any implicit
    # origin path from the prefix.  If there is no prefix (e.g. the empty
    # string), we'll purge everything in the distribution.  Top-level keys
    # require a leading slash for proper invalidation.
    purge_prefix = "/%s*" % remove_origin_path(origin, prefix)

    print("Purging %s from CloudFront distribution %s (%s)… " % (purge_prefix, distribution_domain, distribution_id),
        end = "", flush = True)

    # Send the invalidation request.
    #
    # This is purposely a single path invalidation due to how AWS charges:
    #    https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html
    invalidation = cloudfront.create_invalidation(
        DistributionId    = distribution_id,
        InvalidationBatch = {
            "Paths": {
                "Quantity": 1,
                "Items": [ purge_prefix ]
            },
            "CallerReference": str(time())
        })

    # Wait up to 2 minutes for the invalidation to complete so we know it happened.
    invalidation_id = invalidation["Invalidation"]["Id"]
    waiter_config = {
        "Delay": 5,         # seconds
        "MaxAttempts": 12 * 2,
    }

    start = time()

    try:
        cloudfront.get_waiter('invalidation_completed').wait(
            Id             = invalidation_id,
            DistributionId = distribution_id,
            WaiterConfig   = waiter_config)
    except WaiterError as e:
        print("not yet complete")
        warn("Warning: Invalidation %s did not complete within %ds, but it will probably do so soon."
            % (invalidation_id, waiter_config["Delay"] * waiter_config["MaxAttempts"]))
    else:
        print("done (in %.0fs)" % (time() - start))


def distribution_origins_for_bucket(cloudfront, bucket_name, prefix):
    """
    Return a list of (distribution, origin) tuples from CloudFront where the
    origin points at the given S3 bucket name and path (key) prefix.
    """
    return [
        (distribution, origin)
            for distribution in distributions(cloudfront)
            for origin       in origins(distribution)
                 if origin_is_s3_bucket(origin, bucket_name)
                and origin_path_includes(origin, prefix)
    ]


def distributions(cloudfront):
    """
    Return all CloudFront distributions for the authenticated account.
    """
    return [
        distribution
            for resultset in cloudfront.get_paginator("list_distributions").paginate()
            for distribution in resultset["DistributionList"]["Items"]
    ]


def domain_names(distribution):
    """
    Return a list of domain names for a distribution.

    Aliases, if any, come before the assigned domain and are sorted by length,
    shortest first.
    """
    return [
        *sorted([ alias for alias in distribution["Aliases"]["Items"] ], key = len),
        distribution["DomainName"],
    ]


def origins(distribution):
    """
    Return all origins for a distribution.
    """
    return distribution["Origins"]["Items"]


def origin_is_s3_bucket(origin: dict, bucket_name: str) -> bool:
    """
    Test if the origin appears to point at an S3 bucket with the given name.

    The logic is very similar to how the aws cli detects distributions with S3
    origins:

      https://github.com/aws/aws-cli/blob/50cb347/awscli/customizations/cloudfront.py#L134-L138

    We are a little looser than that code because we have a slightly different
    purpose.  We want to know if the origin is _any_ S3 bucket, not just if the
    CloudFront backend will fetch via the S3 API or not.
    """
    pattern = '^' + re.escape(bucket_name) + r'\.s3[^.]*\.amazonaws\.com$'
    return re.search(pattern, origin["DomainName"]) is not None


def origin_path_includes(origin: dict, prefix: str) -> bool:
    """
    Test if the origin's path includes the given prefix path.

    While this test wouldn't hold for normal filesystem paths (because the
    origin path might only match part of a prefix directory name), S3 paths
    ("keys") are really just strings so pure string prefix matching is correct.
    """
    return prefix.startswith(origin["OriginPath"].lstrip("/"))


def remove_origin_path(origin: dict, prefix: str) -> str:
    """
    Return the given prefix stripped of any implicit distribution origin path.
    """
    return remove_prefix(origin["OriginPath"].lstrip("/"), prefix)

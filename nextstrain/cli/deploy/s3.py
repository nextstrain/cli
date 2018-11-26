"""
Deploy to S3 with automatic CloudFront invalidation.

Backend module for the deploy command.
"""

import boto3
import re
import shutil
import urllib.parse
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, WaiterError
from gzip import GzipFile
from io import BytesIO
from os.path import commonprefix
from pathlib import Path
from time import time
from typing import List
from .. import aws
from ..util import warn, remove_prefix


def run(url: urllib.parse.ParseResult, local_files: List[Path]) -> int:
    # Require a bucket name
    if not url.netloc:
        warn("No bucket name specified in url (%s)" % url.geturl())
        return 1

    # Remove leading slashes from any destination path in order to use it as a
    # prefix for uploaded files.  Internal and trailing slashes are untouched.
    prefix = url.path.lstrip("/")

    # Find the bucket and ensure it already exists so we don't automagically
    # create new buckets.
    try:
        bucket = boto3.resource("s3").Bucket(url.netloc)
        bucket.load()
    except (NoCredentialsError, PartialCredentialsError) as error:
        warn("Error:", error)
        return 1

    if not bucket.creation_date:
        warn('No bucket exists with the name "%s".' % bucket.name)
        warn()
        warn("Buckets are not automatically created for safety reasons.")
        return 1

    # Upload files
    remote_files = upload(local_files, bucket, prefix)

    # Purge any CloudFront caches for this bucket
    purge_cloudfront(bucket, remote_files)

    return 0


def upload(local_files: List[Path], bucket, prefix: str) -> List[str]:
    """
    Upload a set of local file paths to the given bucket under a specified
    prefix.

    Returns a list of remote file names.
    """

    # Create a set of (local name, remote name) tuples.  S3 is a key-value
    # store, not a filesystem, so this remote name prefixing is intentionally a
    # pure string prefix instead of a path-based prefix (which assumes
    # directory structure semantics).
    files = list(zip(local_files, [ prefix + f.name for f in local_files ]))

    for local_file, remote_file in files:
        print("Deploying", local_file, "as", remote_file)

        # Upload compressed data
        with local_file.open("rb") as data, gzip_stream(data) as gzdata:
            bucket.upload_fileobj(
                gzdata,
                remote_file,
                { "ContentType": "application/json", "ContentEncoding": "gzip" })

    return [ remote for local, remote in files ]


def gzip_stream(stream):
    """
    Takes an IO stream and compresses it in-memory with gzip.  Returns a
    BytesIO stream of compressed data.
    """
    gzstream = BytesIO()

    # Pass the original contents through gzip into memory
    with GzipFile(fileobj = gzstream, mode = "wb") as gzfile:
        shutil.copyfileobj(stream, gzfile)

    # Re-seek the compressed data to the start
    gzstream.seek(0)

    return gzstream


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

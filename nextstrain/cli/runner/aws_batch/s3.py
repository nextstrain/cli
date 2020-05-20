"""
S3 handling for AWS Batch jobs.
"""

import binascii
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from calendar import timegm
from os import utime
from pathlib import Path
from tempfile import TemporaryFile
from time import struct_time
from typing import Callable, Generator, Iterable, Optional
from urllib.parse import urlparse
from zipfile import ZipFile, ZipInfo
from ...types import S3Bucket, S3Object


PathMatcher = Callable[[Path], bool]


def object_url(object: S3Object) -> str:
    return "s3://{object.bucket_name}/{object.key}".format_map(locals())


def object_from_url(s3url: str) -> S3Object:
    url = urlparse(s3url)
    key = url.path.lstrip("/")

    assert url.scheme == "s3", \
        "Object URL %s has scheme %s://, not s3://" % (s3url, url.scheme)
    assert url.netloc, "Object URL %s is missing a bucket name" % s3url
    assert key, "Object URL %s is missing an object path/key" % s3url

    return bucket(url.netloc).Object(key)


def upload_workdir(workdir: Path, bucket: S3Bucket, run_id: str) -> S3Object:
    """
    Upload a ZIP archive of the local *workdir* to the remote S3 *bucket* for
    the given *run_id*.

    Returns the S3.Object instance of the uploaded archive.
    """

    remote_workdir = bucket.Object(run_id + ".zip")

    excluded = path_matcher([
        # Jobs don't use .git, so save the bandwidth/space/time.  It may also
        # contain information in history that shouldn't be uploaded.
        ".git/",

        # Don't let the local Snakemake's state interfere with the remote job or
        # vice versa.
        ".snakemake/",

        # Sensitive data is often stored in environment.sh files
        "environment*"
    ])

    # Create a temporary zip file of the workdir…
    with TemporaryFile() as tmpfile:
        with ZipFile(tmpfile, "w") as zipfile:
            for path in walk(workdir, excluded):
                zipfile.write(str(path), str(path.relative_to(workdir)))
                print("zipped:", path)

        # …and upload it to S3
        tmpfile.seek(0)
        remote_workdir.upload_fileobj(tmpfile)

    return remote_workdir


def download_workdir(remote_workdir: S3Object, workdir: Path) -> None:
    """
    Download the *remote_workdir* archive into the local *workdir*.

    The remote workdir's files **overwrite** local files!
    """

    excluded = path_matcher([
        # Jobs don't use .git and it may also contain information that
        # shouldn't be uploaded.
        ".git/",

        # We don't want the remote Snakemake state to interfere locally…
        ".snakemake/",
    ])

    included = path_matcher([
        # But we do want the Snakemake logs to come over.
        ".snakemake/log/",
    ])

    # Download remote zip to temporary file…
    with TemporaryFile() as tmpfile:
        remote_workdir.download_fileobj(tmpfile)
        tmpfile.seek(0)

        # …and extract its contents to the workdir.
        with ZipFile(tmpfile) as zipfile:
            for member in zipfile.infolist():
                path = Path(member.filename)

                # Inclusions negate exclusions but aren't an exhaustive
                # list of what is included.
                if included(path) or not excluded(path):

                    # Only extract files which are different, replacing the
                    # local file with the zipped file.  Note that this means
                    # that empty directories present in the archive but not
                    # locally are never created.
                    if member.CRC != crc32(workdir / path):
                        zipfile.extract(member, str(workdir))

                        # Update atime and mtime from the zip member; it's a
                        # bit boggling that .extract() doesn't handle this,
                        # even optionally.
                        mtime = zipinfo_mtime(member)
                        utime(str(workdir / path), (mtime, mtime))

                        print("unzipped:", workdir / path)


def walk(path: Path, excluded: PathMatcher = lambda x: False) -> Generator[Path, None, None]:
    """
    Iterate over a directory tree (depth-first) starting from *path*, excluding
    any paths matched by *excluded*.
    """
    if not excluded(path):
        yield path

        if path.is_dir():
            for child in path.iterdir():
                yield from walk(child, excluded)


def path_matcher(patterns: Iterable[str]) -> PathMatcher:
    """
    Generate a function which matches a Path object against the list of glob
    *patterns*.
    """
    def matches(path: Path) -> bool:
        return any(map(path.match, patterns))

    return matches


def crc32(path) -> Optional[int]:
    """
    Compute the CRC-32 checksum of the given *path*, consistent with
    checksums stored in a ZIP file.

    Returns None if *path* does not exist.
    """
    if path.exists():
        crc = 0

        # Directories always return 0, matching the behaviour of the CRC
        # attribute of ZipInfo members.
        if not path.is_dir():
            with path.open("rb") as data:
                for chunk in iter(lambda: data.read(1024), b""):
                    crc = binascii.crc32(chunk, crc)

        return crc
    else:
        return None


def zipinfo_mtime(member: ZipInfo) -> float:
    """
    Return the mtime, in seconds since the Unix epoch, of the given
    :class:`zipfile.ZipInfo` *member*.

    Assumes the zip file was created using GMT/UTC!
    """
    # The argument to struct_time() is a 9-tuple, the first 6 values of which
    # we can get from the zip member. The rest, filled with bogus -1
    # placeholders, are tm_wday (day of week), tm_yday (day of year), and
    # tm_isdst (DST flag).
    return timegm(struct_time((*member.date_time, -1, -1, -1)))


def bucket(name: str) -> S3Bucket:
    """
    Load an **existing** bucket from S3.
    """
    config = Config(retries = {'max_attempts': 3})
    s3_resource = boto3.resource("s3", config = config)

    try:
        s3_resource.meta.client.head_bucket(Bucket = name)
    except ClientError:
        raise ValueError('Bucket named "%s" does not exist' % name)

    return s3_resource.Bucket(name)


def bucket_exists(name: str) -> bool:
    """
    Test if an S3 bucket exists.
    """
    try:
        bucket(name)
    except:
        return False
    else:
        return True

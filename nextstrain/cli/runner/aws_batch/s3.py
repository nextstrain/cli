"""
S3 handling for AWS Batch jobs.
"""

import binascii
import boto3
import time
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, Callable, Generator, Iterable, Optional
from zipfile import ZipFile


PathMatcher = Callable[[Path], bool]

# Cleaner-reading type annotations for boto3 S3 objects, which maybe can be
# improved later.  The actual types are generated at runtime in
# boto3.resources.factory, which means we can't use them here easily.  :(
S3Bucket = Any
S3Object = Any


def object_url(object: S3Object) -> str:
    return "s3://{object.bucket_name}/{object.key}".format_map(locals())


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


def bucket(name: str) -> S3Bucket:
    """
    Load an **existing** bucket from S3.
    """
    bucket = boto3.resource("s3").Bucket(name)
    bucket.load()

    if not bucket.creation_date:
        raise ValueError('Bucket named "%s" does not exist' % bucket.name)

    return bucket


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

"""
S3 handling for AWS Batch jobs.
"""

import binascii
import boto3
import fsspec
import os.path
from botocore.config import Config
from botocore.exceptions import ClientError
from calendar import timegm
from os import utime
from pathlib import Path, PurePath
from time import struct_time
from typing import Callable, Generator, Iterable, List, Optional, Any, Union
from urllib.parse import urlparse
from zipfile import ZipFile, ZipInfo
from ... import env
from ...debug import DEBUGGING
from ...types import Env, S3Bucket, S3Object
from ...util import glob_matcher
from ...volume import NamedVolume


PathMatcher = Callable[[Union[Path, PurePath]], bool]


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


def upload_workdir(workdir: Path, bucket: S3Bucket, run_id: str, patterns: List[str] = None, volumes: List[NamedVolume] = []) -> S3Object:
    """
    Upload a ZIP archive of the local *workdir* (and optional *volumes*) to the
    remote S3 *bucket* for the given *run_id*.

    An optional list of *patterns* (shell-style advanced globs) can be passed
    to selectively exclude part of the local *workdir* from being uploaded.

    Returns the S3.Object instance of the uploaded archive.
    """

    remote_workdir = bucket.Object(run_id + ".zip")

    always_excluded = path_matcher([
        # Jobs don't use .git, so save the bandwidth/space/time.  It may also
        # contain information in history that shouldn't be uploaded.
        ".git/",

        # Don't let the local Snakemake's state interfere with the remote job or
        # vice versa.
        ".snakemake/",

        # Sensitive data is often stored in environment.sh files
        "environment*",

        # Ignore Python bytecode
        "*.pyc",
        "__pycache__/",
    ])

    if patterns:
        deselected = glob_matcher(patterns, root = workdir)
    else:
        deselected = lambda path: False

    excluded = lambda path: always_excluded(path) or deselected(path)

    # Stream writes directly to the remote ZIP file
    remote_file: Any
    with fsspec.open(object_url(remote_workdir), "wb", auto_mkdir = False) as remote_file:
        with ZipFile(remote_file, "w") as zipfile:
            for path in walk(workdir, excluded):
                dst = path.relative_to(workdir)
                print(f"zipping: {path}" + (f" (as {dst})" if DEBUGGING else ""))
                zipfile.write(str(path), dst)

            for volume in volumes:
                # XXX TODO: Use the "walk_up" argument to Path.relative_to()
                # once we require Python 3.12.
                #   -trs, 10 Feb 2025
                try:
                    prefix = PurePath(volume.name).relative_to("build")
                except ValueError:
                    prefix = PurePath("..", volume.name)

                for path in walk(volume.src, always_excluded):
                    dst = prefix / path.relative_to(volume.src)
                    print(f"zipping: {path}" + (f" (as {dst})" if DEBUGGING else ""))
                    zipfile.write(str(path), dst)

    return remote_workdir


def download_workdir(remote_workdir: S3Object, workdir: Path, patterns: List[str] = None) -> None:
    """
    Download the *remote_workdir* archive into the local *workdir*.

    The remote workdir's files **overwrite** local files!

    An optional list of *patterns* (shell-style advanced globs) can be passed
    to selectively download only part of the remote workdir.
    """

    # XXX TODO: Consider extending excluded patterns with the globs from any
    # --exclude-from-upload options given, so that files excluded from upload
    # are by default also excluded from download.  That behaviour would seems
    # sometimes useful but other times confusing.  See also my discussion with
    # Trevor and James about this.¹
    #   -trs, 23 May 2024
    #
    # ¹ <https://bedfordlab.slack.com/archives/C0K3GS3J8/p1715750350029879?thread_ts=1715695506.612949&cid=C0K3GS3J8>

    excluded = path_matcher([
        # Jobs don't use .git and it may also contain information that
        # shouldn't be uploaded.
        ".git/",

        # We don't want the remote Snakemake state to interfere locally…
        ".snakemake/",

        # Ignore Python bytecode
        "*.pyc",
        "__pycache__/",
    ])

    included = path_matcher([
        # But we do want the Snakemake logs to come over…
        ".snakemake/log/",

        # …and the input/output metadata Snakemake tracks (akin to mtimes,
        # which we also preserve).
        ".snakemake/metadata/",
    ])

    if patterns:
        selected = glob_matcher(patterns)
    else:
        selected = lambda path: True

    # Open a seekable handle to the remote ZIP file…
    remote_file: Any
    with fsspec.open(object_url(remote_workdir)) as remote_file:

        # …and extract its contents to the workdir.
        with ZipFile(remote_file) as zipfile:
            # Completely ignore archive members with unsafe paths (absolute or
            # upwards-traversing) instead of relying on zipfile.extract()'s
            # default of munging them to be "safe".  Munging seems more
            # confusing than skipping, and skipping is essential in the case of
            # additional volumes being uploaded in the workdir initially.
            safe_members = [
                (filename, member)
                    for filename, member
                     in ((PurePath(m.filename), m) for m in zipfile.infolist())
                     if not filename.is_absolute()
                    and os.path.pardir not in filename.parts ]

            for path, member in safe_members:
                # Inclusions negate exclusions but aren't an exhaustive
                # list of what is included.
                if selected(path) and (included(path) or not excluded(path)):

                    # Only extract files which are different, replacing the
                    # local file with the zipped file.  Note that this means
                    # that empty directories present in the archive but not
                    # locally are never created.
                    if member.CRC != crc32(workdir / path):
                        print("unzipping:", workdir / path)

                        extracted = zipfile.extract(member, str(workdir))

                        # Update atime and mtime from the zip member; it's a
                        # bit boggling that .extract() doesn't handle this,
                        # even optionally.
                        mtime = zipinfo_mtime(member)
                        utime(extracted, (mtime, mtime))

                        # XXX TODO: Preserve/restore Unix mode (e.g. executable
                        # bit).  Currently not handled by this routine, though
                        # we could if need be; see nextstrain/cli/pathogens.py
                        # for an example.  It doesn't seem necessary for
                        # pathogen builds, however, as 1) we've gone this long
                        # without it and 2) pathogen workflows aren't producing
                        # executables as their primary output.
                        #   -trs, 10 Feb 2025


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
    def matches(path: Union[Path, PurePath]) -> bool:
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


def upload_envd(extra_env: Env, bucket: S3Bucket, run_id: str) -> S3Object:
    """
    Upload a ZIP archive of *extra_env* as an envdir to the remote S3 *bucket*
    for the given *run_id*.

    Returns the S3.Object instance of the uploaded archive.
    """

    remote_zip = bucket.Object(run_id + "-env.d.zip")

    remote_file: Any
    with fsspec.open(object_url(remote_zip), "wb", auto_mkdir = False) as remote_file:
        with ZipFile(remote_file, "w") as zipfile:
            for name, contents in env.to_dir_items(extra_env):
                zipfile.writestr(name, contents)

    return remote_zip


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

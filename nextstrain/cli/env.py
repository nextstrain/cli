"""
Environment variable support.
"""
import os
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple, Union
from .types import Env, EnvItem


Envd = Union[Path, str]


def from_vars(vars: Iterable[str], fallback: Env = os.environ) -> Iterator[EnvItem]:
    """
    Parse an iterable of ``name`` or ``name=value`` strings, yielding (name,
    value) tuples representing environment variables.

    Names without a value will take their value from *fallback*, by default the
    current environment.  A value of ``None`` indicates the variable doesn't
    exist in the current environment.

    >>> dict(from_vars(["a=b", "c", "d"], {"c": "fallback"}))
    {'a': 'b', 'c': 'fallback', 'd': None}
    """
    for var in vars:
        if "=" in var:
            name, value = var.split("=", 1)
        else:
            name, value = var, fallback.get(var, None)

        yield name, value


def from_dirs(envds: List[Envd]) -> Iterator[EnvItem]:
    """
    Read a list of *envd* directories in turn with :func:`from_dir` and yield a
    single stream of (name, value) tuples representing environment variables.

    Purely a convenience function.
    """
    for envd in envds:
        yield from from_dir(envd)


def from_dir(envd: Envd) -> Iterator[EnvItem]:
    """
    Read an *envd* directory like :program:`envdir` does, yielding (name,
    value) tuples representing environment variables.

    >>> from tempfile import TemporaryDirectory
    >>> with TemporaryDirectory() as tmp:
    ...     _ = Path(tmp, "x").write_bytes(b'y z\\n')
    ...     dict(sorted(from_dir(tmp)))
    {'x': 'y z'}

    As in the original :program:`envdir` in daemontools, only the first line of
    each file is read and null bytes in the first line are replaced with
    newlines.

    >>> with TemporaryDirectory() as tmp:
    ...     _ = Path(tmp, "first").write_bytes(b'a\\nb\\nc\\n')
    ...     _ = Path(tmp, "multiple").write_bytes(b'a\\x00b\\x00c\\n')
    ...     dict(sorted(from_dir(tmp)))
    {'first': 'a', 'multiple': 'a\\nb\\nc'}

    A value of ``None`` indicates an empty file, which in the semantics of
    :program:`envdir` means that variable should be removed from the
    environment.  Note that an empty file is different than a file containing
    an empty first line.

    >>> with TemporaryDirectory() as tmp:
    ...     _ = Path(tmp, "none").write_bytes(b'')
    ...     _ = Path(tmp, "emptystr").write_bytes(b'\\n')
    ...     dict(sorted(from_dir(tmp)))
    {'emptystr': '', 'none': None}

    The *envd* directory must contain only files and no files may contain ``=``
    in their names.

    >>> with TemporaryDirectory() as tmp:
    ...     Path(tmp, "d").mkdir()
    ...     dict(from_dir(tmp))
    Traceback (most recent call last):
      ...
    IsADirectoryError: 'd' in envdir ... is a directory, not a file

    >>> with TemporaryDirectory() as tmp:
    ...     _ = Path(tmp, "a=b").write_bytes(b'c\\n')
    ...     dict(from_dir(tmp))
    Traceback (most recent call last):
      ...
    ValueError: illegal environment variable name 'a=b' in envdir ...
    """
    if not isinstance(envd, Path):
        envd = Path(envd)

    assert envd.is_dir(), f"envd {str(envd)!r} is not a directory"

    for file in envd.iterdir():
        # The original envdir in daemontools says, "The [filename] must not
        # contain =."¹ but it doesn't check!  Instead, it blindly passes the
        # filename concatenated with the value to putenv(3).  This results in
        # getenv(3) and equivalents splitting on the = in the filename and thus
        # seeing the wrong env var name.  This sort of requirement that's
        # easily checked by the computer but instead placed on the
        # programmer/user is pretty typical for software of daemontools'
        # vintage.
        #
        # In this more humane age of computing, it seems more useful to have
        # the computer check, and indeed many places do, including:
        #
        #   - libc's setenv(3), in contrast to putenv(3)
        #   - Python's os.environ
        #   - envdir port for Python² (skips instead of errors)
        #
        # So we will here as well.  Erroring early when something is amiss
        # seems better than silently skipping it and someone finding out later,
        # in a context far far away, so let's do that.
        #   -trs, 12 June 2023
        #
        # ¹ <https://cr.yp.to/daemontools/envdir.html>
        # ² <https://pypi.org/project/envdir/>
        if "=" in file.name:
            raise ValueError(f"illegal environment variable name {file.name!r} in envdir {envd}")

        # Daemontools envdir errors on directories, while the Python envdir
        # silently skips them.  As above, erroring seems more appropriate than
        # skipping.  We explicitly check rather than rely on the following
        # open() to fail with errno.EISDIR because on Windows you can open() a
        # directory no problem!  We don't check .is_file() because that is only
        # true for plain files and other kinds of files should still be
        # allowed.
        #   -trs, 12 & 16 June 2023
        if file.is_dir():
            raise IsADirectoryError(f"{file.name!r} in envdir {envd} is a directory, not a file")

        if file.stat().st_size > 0:
            with file.open() as f:
                value = f.readline().rstrip().replace("\0", "\n")
        else:
            value = None

        yield file.name, value


def to_dir(envd: Envd, env: Env):
    """
    Write *env* to an *envd* directory like read by :func:`from_dir` and
    :program:`envdir`.

    >>> from tempfile import TemporaryDirectory
    >>> tmp = TemporaryDirectory()
    >>> env = {"x": "y", "multiline": "a\\nb\\nc", "emptystr": "", "none": None}
    >>> to_dir(tmp.name, env)

    >>> env == dict(from_dir(tmp.name))
    True

    >>> sorted(f.name for f in Path(tmp.name).iterdir())
    ['emptystr', 'multiline', 'none', 'x']
    >>> Path(tmp.name, "x").read_bytes()
    b'y\\n'
    >>> Path(tmp.name, "multiline").read_bytes()
    b'a\\x00b\\x00c\\n'
    >>> Path(tmp.name, "emptystr").read_bytes()
    b'\\n'
    >>> Path(tmp.name, "none").read_bytes()
    b''

    The keys of *env* may not contain ``=``.

    >>> to_dir(tmp.name, {"a=b": "c"})
    Traceback (most recent call last):
      ...
    ValueError: illegal environment variable name 'a=b'

    >>> tmp.cleanup()
    """
    if not isinstance(envd, Path):
        envd = Path(envd)

    assert envd.is_dir(), f"envd {str(envd)!r} is not a directory"

    for name, contents in to_dir_items(env):
        with (envd / name).open("wb") as f:
            f.write(contents)


def to_dir_items(env: Env) -> Iterator[Tuple[str, bytes]]:
    """
    Convert *env* to a stream of (name, contents) pairs representing files in
    an *envd* directory like read by :func:`from_dir` and :program:`envdir`.

    >>> env = {"x": "y", "multiline": "a\\nb\\nc", "emptystr": "", "none": None}
    >>> dict(to_dir_items(env))
    {'x': b'y\\n', 'multiline': b'a\\x00b\\x00c\\n', 'emptystr': b'\\n', 'none': b''}

    The keys of *env* may not contain ``=``.

    >>> dict(to_dir_items({"a=b": "c"}))
    Traceback (most recent call last):
      ...
    ValueError: illegal environment variable name 'a=b'
    """
    for name, value in env.items():
        # See rationale for error above.
        if "=" in name:
            raise ValueError(f"illegal environment variable name {name!r}")

        if value is not None:
            yield name, (value.replace("\n", "\0") + "\n").encode("utf-8")
        else:
            yield name, b""

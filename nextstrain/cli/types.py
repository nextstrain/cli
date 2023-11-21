"""
Type definitions for internal use.
"""

import argparse
import builtins
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, List, Mapping, Optional, Tuple, Union
# TODO: Use typing.Protocol once Python 3.8 is the minimum supported version.
# TODO: Use typing.TypeAlias once Python 3.10 is the minimum supported version.
from typing_extensions import Protocol, TypeAlias
# XXX FIXME: causes import cycle; need to sort that out
#from .authn import User
from .volume import NamedVolume
from .url import URL, Origin

# Re-export EllipsisType so we can paper over its absence from older Pythons
if sys.version_info >= (3, 10):
    from types import EllipsisType
else:
    EllipsisType: TypeAlias = 'builtins.ellipsis'

"""
An immutable mapping of (*name*, *value*) pairs representing a set of
additional environment variables to overlay on the current environment (e.g.
when executing a subprocess).

Each (*name*, *value*) pair represents a single environment variable.

A *value* of ``None`` indicates the positive absence of *name* (e.g. it is to
be removed if present).
"""
Env = Mapping['EnvName', 'EnvValue']
EnvItem = Tuple['EnvName', 'EnvValue']
EnvName = str
EnvValue = Union[str, None]

Options = argparse.Namespace

RunnerSetupStatus = Optional[bool]

RunnerTestResults = List['RunnerTestResult']
RunnerTestResult  = Tuple[str, 'RunnerTestResultStatus']
RunnerTestResultStatus: TypeAlias = Union[bool, None, EllipsisType]

RunnerUpdateStatus = Optional[bool]

# Cleaner-reading type annotations for boto3 S3 objects, which maybe can be
# improved later.  The actual types are generated at runtime in
# boto3.resources.factory, which means we can't use them here easily.  :(
S3Bucket = Any
S3Object = Any


class RunnerModule(Protocol):
    @staticmethod
    def register_arguments(parser: argparse.ArgumentParser) -> None: ...

    @staticmethod
    def run(opts: Options,
            argv: List[str],
            working_volume: Optional[NamedVolume],
            extra_env: Env,
            cpus: Optional[int],
            memory: Optional[int]) -> int:
        ...

    @staticmethod
    def setup(dry_run: bool = False, force: bool = False) -> RunnerSetupStatus: ...

    @staticmethod
    def test_setup() -> RunnerTestResults: ...

    @staticmethod
    def set_default_config() -> None: ...

    @staticmethod
    def update() -> RunnerUpdateStatus: ...

    @staticmethod
    def versions() -> Iterable[str]: ...


class RemoteModule(Protocol):
    @staticmethod
    def upload(url: URL, local_files: List[Path], dry_run: bool = False) -> Iterable[Tuple[Path, str]]: ...

    @staticmethod
    def download(url: URL, local_path: Path, recursively: bool = False, dry_run: bool = False) -> Iterable[Tuple[str, Path]]: ...

    @staticmethod
    def ls(url: URL) -> Iterable[str]: ...

    @staticmethod
    def delete(url: URL, recursively: bool = False, dry_run: bool = False) -> Iterable[str]: ...

    @staticmethod
    def current_user(origin: Origin) -> Optional['User']: ...

    @staticmethod
    def login(origin: Origin, credentials: Optional[Callable[[], Tuple[str, str]]] = None) -> 'User': ...

    @staticmethod
    def renew(origin: Origin) -> Optional['User']: ...

    @staticmethod
    def logout(origin: Origin): ...

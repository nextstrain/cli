"""
Type definitions for internal use.
"""

import argparse
from pathlib import Path
from typing import Any, Callable, Iterable, List, Mapping, Optional, Protocol, Tuple, TypeAlias, Union, TYPE_CHECKING, runtime_checkable

# Import concrete types from our other modules only during type checking to
# avoid import cycles during runtime.
if TYPE_CHECKING:
    from .authn import User
    from .volume import NamedVolume
    from .url import URL, Origin

from types import EllipsisType

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

SetupStatus = Optional[bool]

SetupTestResults = Iterable['SetupTestResult']
SetupTestResult  = Tuple[str, 'SetupTestResultStatus']
SetupTestResultStatus: TypeAlias = Union[bool, None, EllipsisType]

UpdateStatus = Optional[bool]

# Re-export boto3 S3 resource types we use for convenience.
if TYPE_CHECKING:
    from types_boto3_s3.service_resource import Bucket as S3Bucket, Object as S3Object # noqa: F401 (for re-export)
else:
    S3Bucket = Any
    S3Object = Any


@runtime_checkable
class RunnerModule(Protocol):
    @staticmethod
    def register_arguments(parser: argparse.ArgumentParser) -> None: ...

    @staticmethod
    def run(opts: Options,
            argv: List[str],
            working_volume: Optional['NamedVolume'],
            extra_env: Env,
            cpus: Optional[int],
            memory: Optional[int]) -> int:
        ...

    @staticmethod
    def setup(dry_run: bool = False, force: bool = False) -> SetupStatus: ...

    @staticmethod
    def test_setup() -> SetupTestResults: ...

    @staticmethod
    def set_default_config() -> None: ...

    @staticmethod
    def update() -> UpdateStatus: ...

    @staticmethod
    def versions() -> Iterable[str]: ...


class RemoteModule(Protocol):
    @staticmethod
    def upload(url: 'URL', local_files: List[Path], dry_run: bool = False) -> Iterable[Tuple[Path, str]]: ...

    @staticmethod
    def download(url: 'URL', local_path: Path, recursively: bool = False, dry_run: bool = False) -> Iterable[Tuple[str, Path]]: ...

    @staticmethod
    def ls(url: 'URL') -> Iterable[str]: ...

    @staticmethod
    def delete(url: 'URL', recursively: bool = False, dry_run: bool = False) -> Iterable[str]: ...

    @staticmethod
    def current_user(origin: 'Origin') -> Optional['User']: ...

    @staticmethod
    def login(origin: 'Origin', credentials: Optional[Callable[[], Tuple[str, str]]] = None) -> 'User': ...

    @staticmethod
    def renew(origin: 'Origin') -> Optional['User']: ...

    @staticmethod
    def logout(origin: 'Origin'): ...

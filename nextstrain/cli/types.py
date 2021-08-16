"""
Type definitions for internal use.
"""

import argparse
import builtins
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, List, Mapping, Optional, Tuple, Union
from typing_extensions import Protocol
from .volume import NamedVolume

Options = argparse.Namespace

RunnerTestResults = List['RunnerTestResult']
RunnerTestResult  = Tuple[str, 'RunnerTestResultStatus']
RunnerTestResultStatus = Union[bool, None, 'builtins.ellipsis']

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
            extra_env: Mapping,
            cpus: Optional[int],
            memory: Optional[int]) -> int:
        ...

    @staticmethod
    def test_setup() -> Any: ...

    @staticmethod
    def update() -> bool: ...

    @staticmethod
    def versions() -> Iterable[str]: ...


class RemoteModule(Protocol):
    @staticmethod
    def upload(url: urllib.parse.ParseResult, local_files: List[Path]) -> Iterable[Tuple[Path, Path]]: ...

    @staticmethod
    def download(url: urllib.parse.ParseResult, local_path: Path, recursively: bool = False) -> Iterable[Tuple[Path, Path]]: ...

    @staticmethod
    def ls(url: urllib.parse.ParseResult) -> Iterable[Path]: ...

    @staticmethod
    def delete(url: urllib.parse.ParseResult, recursively: bool = False) -> Iterable[Path]: ...

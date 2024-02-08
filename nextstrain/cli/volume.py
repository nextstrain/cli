"""
Volumes map well-known names to a source path.
"""

import argparse
from typing import NamedTuple
from pathlib import Path


class NamedVolume(NamedTuple):
    name: str
    src: Path
    dir: bool = True
    writable: bool = True


def store_volume(volume_name):
    """
    Generates and returns an argparse.Action subclass for storing named volume
    tuples.

    Multiple argparse arguments can use this to cooperatively accept source
    path definitions for named volumes.

    Each named volume is stored as a NamedTuple (name, src).  The tuple is
    stored on the options object as an element in a shared list of volumes,
    accessible via the "volumes" attribute on the options object.

    For convenient path manipulation and testing, the "src" value is stored as
    a Path object.
    """
    class store(argparse.Action):
        def __call__(self, parser, namespace, values, option_strings = None):
            # Add the new volume to the list of volumes
            volumes    = getattr(namespace, "volumes", [])
            new_volume = NamedVolume(volume_name, Path(values)) if values else None
            setattr(namespace, "volumes", [*volumes, new_volume])

    return store

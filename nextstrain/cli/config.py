"""
Configuration file handling.
"""

import os
import stat
from configparser import ConfigParser
from contextlib import contextmanager
from fasteners import InterProcessReaderWriterLock
from pathlib import Path
from typing import Optional


# Not finding a homedir is unlikely, but possible.  Fallback to the current
# directory.
try:
    HOME = Path.home()
except:
    HOME = Path(".")

# Path to our config file
CONFIG = Path(os.environ.get("NEXTSTRAIN_CONFIG") or
              HOME / ".nextstrain/config")

# Path to our secrets file
SECRETS = Path(os.environ.get("NEXTSTRAIN_SECRETS") or
               HOME / ".nextstrain/secrets")

# Permissions to use for the secrets file if we have to create it.
SECRETS_PERMS = \
    ( stat.S_IRUSR  # u+r
    | stat.S_IWUSR  # u+w
    )               # u=rw,go=


def load(path: Path = CONFIG) -> ConfigParser:
    """
    Load the config file at *path* and return a ConfigParser object.

    If *path* does not exist, no error is raised, but an empty ConfigParser
    object is returned.  This is the default behaviour of ConfigParser and
    intended so that a missing config file isn't fatal.
    """
    config = ConfigParser()
    config.read(str(path), encoding = "utf-8")
    return config


def save(config, path: Path = CONFIG):
    """
    Write the *config* object to *path*.

    If the immediate parent directory of the file named by *path* is
    ``.nextstrain``, then that directory will be created if it does not already
    exist.
    """
    secrets = path is SECRETS

    # See also the handling of parents in write_lock().
    path = path.resolve(strict = False)

    if path.parent.name == ".nextstrain":
        path.parent.mkdir(exist_ok = True)

    if secrets:
        if path.exists():
            path.chmod(SECRETS_PERMS)
        else:
            path.touch(SECRETS_PERMS)

    with path.open(mode = "w", encoding = "utf-8") as file:
        config.write(file)


def get(section: str, field: str, fallback: str = None, path: Path = CONFIG) -> Optional[str]:
    """
    Return *field* from *section* in the config file at the given *path*.

    If *section* or *field* does not exist, returns *fallback* (which defaults
    to None).
    """
    with read_lock(path):
        config = load(path)

        if section in config:
            return config[section].get(field, fallback)
        else:
            return fallback


def set(section: str, field: str, value: str, path: Path = CONFIG):
    """
    Set *field* in *section* to *value* in the config file at the given *path*.

    If *section* does not exist, it is automatically created.
    """
    with write_lock(path):
        config = load(path)

        if section not in config:
            config.add_section(section)

        config.set(section, field, value)

        save(config, path)


def remove(section: str, path: Path) -> bool:
    """
    Remove the *section* in the config file at the given *path*.

    Returns ``True`` when *section* is removed.  Returns ``False`` if *section*
    or *path* does not exist.
    """
    if not path.exists():
        return False

    with write_lock(path):
        config = load(path)

        if section not in config:
            return False

        del config[section]

        save(config, path)

    return True


@contextmanager
def read_lock(path: Path):
    """
    Lock *path* for reading across processes (but not within).

    Uses advisory/cooperative locks.  Avoids creating *path* if it does not
    exist.
    """
    if path.exists():
        with InterProcessReaderWriterLock(path).read_lock():
            yield
    else:
        yield


@contextmanager
def write_lock(path: Path):
    """
    Lock *path* for writing across processes (but not within).

    Uses advisory/cooperative locks.  Avoids creating *path* if the parent does
    not exist.
    """
    # We only care if the parent exists, as the file is expected to be written
    # and created if it does not exist.
    parent = path.resolve(strict = False).parent

    if parent.name == ".nextstrain":
        # save() will auto-create in this case, so look one parent higher.
        parent = parent.parent

    if parent.exists():
        with InterProcessReaderWriterLock(path).write_lock():
            yield
    else:
        yield

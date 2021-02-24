"""
Configuration file handling.
"""

import os
from configparser import ConfigParser
from pathlib import Path
from typing import Optional


# Not finding a homedir is unlikely, but possible.  Fallback to the current
# directory.
try:
    HOME = Path.home()
except:
    HOME = Path(".")

# Path to our config file
PATH = Path(os.environ.get("NEXTSTRAIN_CONFIG") or
            HOME / ".nextstrain/config")



def load(path: Path = PATH) -> ConfigParser:
    """
    Load the config file at *path* and return a ConfigParser object.
    """
    config = ConfigParser()
    config.read(str(path), encoding = "utf-8")
    return config


def save(config, path: Path = PATH):
    """
    Write the *config* object to *path*.

    If the immediate parent directory of the file named by *path* is
    ``.nextstrain``, then that directory will be created if it does not already
    exist.
    """
    if path.parent.name == ".nextstrain":
        path.parent.mkdir(exist_ok = True)

    with path.open(mode = "w", encoding = "utf-8") as file:
        config.write(file)


def get(section: str, field: str, fallback: str = None,
    path: Path = PATH) -> Optional[str]:
    """
    Return *field* from *section* in the config file at the given *path*.

    If *section* or *field* does not exist, returns *fallback* (which defaults
    to None).
    """
    config = load(path)

    if section in config:
        return config[section].get(field, fallback)
    else:
        return fallback


def set(section: str, field: str, value: str, path: Path = PATH):
    """
    Set *field* in *section* to *value* in the config file at the given *path*.

    If *section* does not exist, it is automatically created.
    """
    config = load(path)

    if section not in config:
        config.add_section(section)

    config.set(section, field, value)

    save(config, path)

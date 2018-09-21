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


def load(path = PATH) -> ConfigParser:
    """
    Load the config file at *path* and return a ConfigParser object.
    """
    config = ConfigParser()
    config.read(str(path), encoding = "utf-8")
    return config


def save(config, path = PATH):
    """
    Write the *config* object to *path*.

    The immediate parent directory of the file named by *path* will be created
    if it does not exist.  This supports the last two components of the path
    being ``…/.nextstrain/config`` when the ``.nextstrain`` directory may not
    already exist.
    """
    path.resolve().parent.mkdir(exist_ok = True)

    with path.open(mode = "w", encoding = "utf-8") as file:
        config.write(file)


def get(section: str, field: str, fallback: str = None) -> Optional[str]:
    """
    Return *field* from *section* in the default config file.

    If *section* or *field* does not exist, returns *fallback* (which defaults
    to None).
    """
    config = load()

    if section in config:
        return config[section].get(field, fallback)
    else:
        return fallback


def set(section: str, field: str, value: str):
    """
    Set *field* in *section* to *value* in the default config file.

    If *section* does not exist, it is automatically created.
    """
    config = load()

    if section not in config:
        config.add_section(section)

    config.set(section, field, value)

    save(config)

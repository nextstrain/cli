"""
Filesystem paths.
"""
import os
from pathlib import Path
from typing import Union


def from_env(name: str, default: Union[str, Path]) -> Path:
    """
    Wrap a :py:cls:`Path` around the value of the environment variable *name*,
    if any, otherwise *default*.

    Environment variables which are set but empty will be treated as unset
    (i.e. *default* will be used).
    """
    return Path(os.environ.get(name) or default)


# Not finding a homedir is unlikely, but possible.  Fallback to the current
# directory.
try:
    HOME = Path.home()
except:
    HOME = Path(".")

# Path to our config file
CONFIG = from_env("NEXTSTRAIN_CONFIG", HOME / ".nextstrain/config")

# Path to our secrets file
SECRETS = from_env("NEXTSTRAIN_SECRETS", HOME / ".nextstrain/secrets")

# Path to our global lock file
LOCK = from_env("NEXTSTRAIN_LOCK", HOME / ".nextstrain/lock")

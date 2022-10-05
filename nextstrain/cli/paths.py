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


# Path to our config/app data dir
NEXTSTRAIN_HOME = from_env("NEXTSTRAIN_HOME", HOME / ".nextstrain/")

# Path to runtime data dirs
RUNTIMES = from_env("NEXTSTRAIN_RUNTIMES", NEXTSTRAIN_HOME / "runtimes/")

# Path to our config file
CONFIG = from_env("NEXTSTRAIN_CONFIG", NEXTSTRAIN_HOME / "config")

# Path to our secrets file
SECRETS = from_env("NEXTSTRAIN_SECRETS", NEXTSTRAIN_HOME / "secrets")

# Path to our global lock file
LOCK = from_env("NEXTSTRAIN_LOCK", NEXTSTRAIN_HOME / "lock")

# Path to our shell history file
SHELL_HISTORY = from_env("NEXTSTRAIN_SHELL_HISTORY", NEXTSTRAIN_HOME / "shell-history")

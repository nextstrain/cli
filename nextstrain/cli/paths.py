"""
Filesystem paths.
"""
import os
from pathlib import Path


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

# Path to our global lock file
LOCK = Path(os.environ.get("NEXTSTRAIN_LOCK") or
            HOME / ".nextstrain/lock")

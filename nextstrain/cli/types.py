"""
Type aliases for internal use.
"""

import argparse
import builtins
from typing import Any, List, Tuple, Union

Options = argparse.Namespace

RunnerTestResult  = Tuple[str, Union[bool, None, 'builtins.ellipsis']]
RunnerTestResults = List[RunnerTestResult]

# Cleaner-reading type annotations for boto3 S3 objects, which maybe can be
# improved later.  The actual types are generated at runtime in
# boto3.resources.factory, which means we can't use them here easily.  :(
S3Bucket = Any
S3Object = Any

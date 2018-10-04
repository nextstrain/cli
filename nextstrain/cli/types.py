"""
Type aliases for internal use.
"""

import argparse
import builtins
from typing import List, Tuple, Union

Options = argparse.Namespace

RunnerTestResult  = Tuple[str, Union[bool, None, 'builtins.ellipsis']]
RunnerTestResults = List[RunnerTestResult]

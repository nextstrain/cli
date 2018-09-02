"""
Type aliases for internal use.
"""

import argparse
from typing import List, Tuple

Options = argparse.Namespace

RunnerTestResult  = Tuple[str, bool]
RunnerTestResults = List[RunnerTestResult]

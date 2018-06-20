"""
Stub function and module used as a setuptools entry point.
"""

from sys import argv, exit
from nextstrain import cli

# Entry point for setuptools-installed script.
def main():
    return cli.run( argv[1:] )

# Run when called as `python -m nextstrain.cli`, here for good measure.
if __name__ == "__main__":
    exit( main() )

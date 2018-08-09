from ..__version__ import __version__
from .. import __package__ as __top_package__
from ..runner import all_runners

def register_parser(subparser):
    return subparser.add_parser(
        "version",

        # Description of command in top-level --help
        help = "Show version information",

        # Don't add a --help option to this command
        add_help = False
    )

def run(opts):
    print(__top_package__, __version__)

    for runner in all_runners:
        runner.print_version()

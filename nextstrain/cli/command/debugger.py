"""
Launch pdb from within the Nextstrain CLI process.

This is a development and troubleshooting tool unnecessary for normal usage.
"""
import pdb


def register_parser(subparser):
    parser = subparser.add_parser("debugger", help = "Start a debugger")
    return parser


def run(opts):
    pdb.set_trace()

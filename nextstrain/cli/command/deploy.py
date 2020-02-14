# This command, `nextstrain deploy`, is now an alias for `nextstrain remote
# upload`.
#
# Registering our own parser lets us preserve the original short description
# and avoids introducing "upload" as a top-level command.

from textwrap import dedent
from .remote.upload import register_arguments, run, __doc__

def register_parser(subparser):
    parser = subparser.add_parser("deploy", help = "Deploy pathogen build")
    register_arguments(parser)
    return parser

def insert_paragraph(text, index, insert):
    paras = text.split("\n\n")
    paras.insert(index, dedent(insert))
    return "\n\n".join(paras)

__doc__ = insert_paragraph(
    __doc__, 1, """
    The `nextstrain deploy` command is an alias for `nextstrain remote upload`.
    """)

# This command, `nextstrain deploy`, is now an alias for `nextstrain remote
# upload`.
#
# Registering our own parser lets us preserve the original short description
# and avoids introducing "upload" as a top-level command.

from .remote.upload import register_arguments, run, __doc__

def register_parser(subparser):
    parser = subparser.add_parser("deploy", help = "Deploy pathogen build")
    register_arguments(parser)
    return parser

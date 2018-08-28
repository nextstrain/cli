"""
Deploys a set of pathogen build JSON data files to a remote location.

nextstrain.org, or other instances of the Nextstrain web frontend (auspice),
fetch the deployed JSON data files for display.
 
 
Destinations
------------

Currently only Amazon S3 buckets (s3://…) are supported as the remote
destination, but others can be added in the future.

Destination URLs support optional path prefixes if you want your local
filenames to be prefixed on the remote destination.  For example:

    nextstrain deploy s3://my-bucket/some/prefix/ auspice/zika*.json

will upload files named "some/prefix/zika*.json".
 
 
Authentication
--------------

Credentials for authentication should generally be provided by environment
variables specific to each destination type.

S3
--

* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY

More information at:

    https://boto3.readthedocs.io/en/latest/guide/configuration.html#environment-variables

A persistent credentials file, ~/.aws/credentials, is also supported:

    https://boto3.readthedocs.io/en/latest/guide/configuration.html#shared-credentials-file
 
"""

from pathlib import Path
from urllib.parse import urlparse
from ..util import warn
from ..deploy import s3


SUPPORTED_SCHEMES = {
    "s3": s3,
}


def register_parser(subparser):
    parser = subparser.add_parser("deploy", help = "Deploy pathogen build")

    # Destination
    parser.add_argument(
        "destination",
        help    = "Deploy destination as a URL, with optional key/path prefix",
        metavar = "<s3://bucket-name>")

    # Files to deploy
    parser.add_argument(
        "files",
        help    = "JSON data files to deploy",
        metavar = "<file.json>",
        nargs   = "+")

    return parser


def run(opts):
    url = urlparse(opts.destination)

    if url.scheme not in SUPPORTED_SCHEMES:
        warn("Error: Unsupported destination scheme %s://" % url.scheme)
        warn("")
        warn("Supported schemes are: %s" % ", ".join(SUPPORTED_SCHEMES))
        return 1

    deploy = SUPPORTED_SCHEMES[url.scheme]
    files  = [Path(f) for f in opts.files]

    return deploy.run(url, files)

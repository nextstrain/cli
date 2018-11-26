"""
boto3 client handling for AWS services.
"""

import boto3
from botocore.exceptions import NoRegionError


DEFAULT_REGION = "us-east-1"


def client_with_default_region(service, default_region = DEFAULT_REGION):
    """
    Return a boto3 client for the named *service* in the *default_region* if no
    region is specified in the default session (via the environment, AWS
    config, or ``boto3.setup_default_session``).
    """
    try:
        return boto3.client(service)
    except NoRegionError:
        return boto3.client(service, region_name = default_region)

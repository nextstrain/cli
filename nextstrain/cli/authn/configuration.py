"""
Authentication configuration.
"""
from functools import lru_cache
from .. import requests
from ..errors import UserError
from ..url import Origin


@lru_cache(maxsize = None)
def openid_configuration(origin: Origin):
    """
    Fetch the OpenID provider configuration/metadata for *origin*.

    While this information is typically served by an OP (OpenID provider), aka
    IdP, here we expect *origin* to be a nextstrain.org-like RP (relying
    party), aka SP (service provider), which is passing along its own IdP/OP's
    configuration for us to discover.
    """
    assert origin

    with requests.Session() as http:
        try:
            response = http.get(origin.rstrip("/") + "/.well-known/openid-configuration")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as err:
            raise UserError(f"""
                Could not connect to {origin} to retrieve
                authentication metadata:

                    {type(err).__name__}: {err}

                That remote may be invalid or you may be experiencing network
                connectivity issues.
                """) from err

        except (requests.exceptions.HTTPError, requests.exceptions.JSONDecodeError) as err:
            raise UserError(f"""
                Failed to retrieve authentication metadata for {origin}:

                    {type(err).__name__}: {err}

                That remote seems unlikely to be an alternate nextstrain.org
                instance or an internal Nextstrain Groups Server instance.
                """) from err


def client_configuration(origin: Origin):
    """
    OpenID client configuration/metadata for *origin*.

    The OpenID provider configuration of a nextstrain.org-like remote includes
    client configuration for Nextstrain CLI.  This details the OpenID client
    that's registered with the corresponding provider for Nextstrain CLI's use.
    """
    assert origin

    config = openid_configuration(origin)

    if "nextstrain_cli_client_configuration" not in config:
        raise UserError(f"""
            Authentication metadata for {origin}
            does not contain required client information for Nextstrain CLI.

            That remote seems unlikely to be an alternate nextstrain.org
            instance or an internal Nextstrain Groups Server instance.
            """)

    return config["nextstrain_cli_client_configuration"]

"""
Authentication configuration.
"""
import requests
from functools import lru_cache
from ..debug import debug
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
        response = http.get(origin.rstrip("/") + "/.well-known/openid-configuration")

        if response.status_code == 404:
            # XXX TODO: This hardcoded fallback is equivalent to what was
            # previously hardcoded in our Cognito-only authentication
            # routines.  Retaining it for now helps ease the use of these
            # newer authn routines in advance of nextstrain.org actually
            # serving /.well-known/openid-configuration.  Once it does,
            # this fallback is ok to remove.
            #   -trs, 21 Nov 2023
            if origin == "https://nextstrain.org":
                debug(f"authn: failed to retrieve authentication metadata for {origin}; using hardcoded fallback…")
                return {
                    "issuer": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Cg5rcTged",
                    "jwks_uri": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Cg5rcTged/.well-known/jwks.json",
                    "authorization_endpoint": "https://login.nextstrain.org/oauth2/authorize",
                    "token_endpoint": "https://login.nextstrain.org/oauth2/token",
                    "scopes_supported": ["openid", "email", "phone", "profile"],
                    "nextstrain_cli_client_configuration": {
                        "aws_cognito_user_pool_id": "us-east-1_Cg5rcTged",
                        "client_id": "2vmc93kj4fiul8uv40uqge93m5",
                        "id_token_username_claim": "cognito:username",
                        "id_token_groups_claim": "cognito:groups",
                    }
                }
            else:
                raise UserError(f"""
                    Failed to retrieve authentication metadata for {origin}.
                    
                    Is seems unlikely to be an alternate nextstrain.org
                    instance or an internal Nextstrain Groups Server instance.
                    """)

        response.raise_for_status()
        return response.json()


def client_configuration(origin: Origin):
    """
    OpenID client configuration/metadata for *origin*.

    The OpenID provider configuration of a nextstrain.org-like remote includes
    client configuration for Nextstrain CLI.  This details the OpenID client
    that's registered with the corresponding provider for Nextstrain CLI's use.
    """
    assert origin
    return openid_configuration(origin)["nextstrain_cli_client_configuration"]

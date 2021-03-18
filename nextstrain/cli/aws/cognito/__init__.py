"""
AWS Cognito helpers.
"""
import boto3
import jwt
import jwt.exceptions

from .srp import CognitoSRP, NewPasswordRequiredError


class CognitoError(Exception):
    """
    Error from Cognito.
    """
    def __init__(self, error):
        try:
            msg = error.response["Error"]["Message"]
        except:
            msg = str(error)
        super().__init__(msg)

class NotAuthorizedError(CognitoError):
    """Not Authorized response from Cognito during authentication."""
    pass

class TokenError(Exception):
    """Error when verifying tokens."""
    pass

class MissingTokenError(TokenError):
    """
    No token provided but one is required.

    Context is the kind of token ("use") that was missing.
    """
    pass

class ExpiredTokenError(TokenError):
    """
    Token is expired.

    Context is the kind of token ("use") that was missing.
    """
    pass

class InvalidUseError(TokenError):
    """
    The "use" of the token does not match the expected value.

    May indicate an accidental token swap.
    """
    pass


class Session:
    """
    Minimal user/password and token authentication session interface around
    :mod:`boto3` ``cognito-idp`` client to abstract away unnecessary details
    from the rest of the codebase.

    Inspired by the similar libraries :mod:`warrant` and :mod:`pycognito`, but
    with a much smaller surface area by not supporting functionality that we
    don't need.  This interface better fits our own use case and aims to be
    hard or impossible to accidentally use insecurely.
    """
    def __init__(self, user_pool_id, client_id):
        self.user_pool_id     = user_pool_id
        self.user_pool_region = self.user_pool_id.split("_")[0]
        self.client_id        = client_id

        self.cognito = boto3.client("cognito-idp", region_name = self.user_pool_region)
        self.jwks    = jwt.PyJWKClient(self.jwks_url)

        self._tokens = {}
        self._claims = {}

    @property
    def user_pool_url(self):
        return f"https://cognito-idp.{self.user_pool_region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self):
        return f"{self.user_pool_url}/.well-known/jwks.json"

    @property
    def id_token(self):
        """
        The id token for this session, set by calling :meth:`.authenticate` or
        `.verify_tokens`.

        Useful for persisting in external storage, but should be treated as an
        opaque value.  The claims embedded in this token are accessible in
        :attr:`.id_claims`.
        """
        return self._tokens.get("id")

    @property
    def access_token(self):
        """
        The access token for this session, set by calling :meth:`.authenticate`
        or `.verify_tokens`.

        Useful for persisting in external storage, but should be treated as an
        opaque value.
        """
        return self._tokens.get("access")

    @property
    def refresh_token(self):
        """
        The refresh token for this session, set by calling :meth:`.authenticate`
        or `.verify_tokens`.

        Useful for persisting in external storage, but should be treated as an
        opaque value.
        """
        return self._tokens.get("refresh")

    @property
    def id_claims(self):
        """
        Dictionary of verified claims from the :attr:`.id_token`.
        """
        return self._claims.get("id")


    def authenticate(self, username, password):
        """
        Authenticates the given *username* and *password* with Cognito using
        the Secure Remote Password protocol.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises a :exc:`CognitoError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        srp = CognitoSRP(
            username    = username,
            password    = password,
            pool_id     = self.user_pool_id,
            client_id   = self.client_id,
            client      = self.cognito)

        try:
            response = srp.authenticate_user()

        except self.cognito.exceptions.NotAuthorizedException as e:
            raise NotAuthorizedError(e)

        result = response.get("AuthenticationResult", {})

        self.verify_tokens(
            id_token      = result.get("IdToken"),
            access_token  = result.get("AccessToken"),
            refresh_token = result.get("RefreshToken"))


    def renew_tokens(self, *, refresh_token):
        """
        Acquires a new :attr:`.id_token` and :attr:`.access_token` pair using
        the given *refresh_token*.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises a :exc:`CognitoError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        if not refresh_token:
            raise MissingTokenError("refresh")

        try:
            response = self.cognito.initiate_auth(
                ClientId       = self.client_id,
                AuthFlow       = "REFRESH_TOKEN_AUTH",
                AuthParameters = {"REFRESH_TOKEN": refresh_token})

        except self.cognito.exceptions.NotAuthorizedException as e:
            raise NotAuthorizedError(e)

        result = response.get("AuthenticationResult", {})

        self.verify_tokens(
            id_token      = result.get("IdToken"),
            access_token  = result.get("AccessToken"),
            refresh_token = refresh_token)


    def verify_tokens(self, *, id_token, access_token, refresh_token):
        """
        Verifies the given *id_token*, *access_token*, and *refresh_token*.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises a :exc:`TokenError` or one of its subclasses.
        """
        if not id_token:
            raise MissingTokenError("id")

        if not access_token:
            raise MissingTokenError("access")

        if not refresh_token:
            raise MissingTokenError("refresh")

        self._verify_token(id_token, "id")
        self._verify_token(access_token, "access")
        self._tokens["refresh"] = refresh_token


    def _verify_token(self, token, use):
        """
        Verifies all aspects of the given *token* (a signed JWT) which is
        expected to be used for the given *use* (``id`` or ``access``).

        Assertions about expected algorithms, audience, issuer, and token use
        follow guidelines from
        <https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html>.
        """
        jwk = self.jwks.get_signing_key_from_jwt(token)

        try:
            claims = jwt.decode(
                token,
                jwk.key,
                algorithms = ["RS256"],
                audience   = self.client_id if use != "access" else None,
                issuer     = self.user_pool_url,
                options    = { "require": ["exp"] })

        except jwt.exceptions.ExpiredSignatureError:
            raise ExpiredTokenError(use)

        except jwt.exceptions.InvalidTokenError as e:
            raise TokenError(f"{type(e).__name__}: {str(e)}")

        claimed_use = claims.get("token_use")

        if claimed_use != use:
            raise InvalidUseError(f"{use} (expected) != {claimed_use} (claimed)")

        self._tokens[use] = token
        self._claims[use] = claims

        return claims

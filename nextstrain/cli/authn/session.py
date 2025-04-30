"""
Authentication sessions.
"""
import boto3
import jwt
import jwt.exceptions
import secrets

from base64 import b64encode
from errno import EADDRINUSE
from hashlib import sha256
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from inspect import cleandoc
from textwrap import fill
from threading import Thread
from typing import Any, Dict, Mapping, Optional, Set

from .. import requests
from ..aws.cognito.srp import CognitoSRP
from ..browser import BROWSER, open_browser
from ..debug import debug
from ..errors import UserError
from ..net import is_loopback
from ..url import URL, Origin, query
from .configuration import openid_configuration, client_configuration
from .errors import NotAuthorizedError, TokenError, MissingTokenError, ExpiredTokenError, InvalidUseError


class Session:
    origin: Origin
    can_authenticate_with_browser: bool = False
    can_authenticate_with_password: bool = False

    def __new__(cls, origin: Origin) -> 'Session':
        assert origin
        if cls is Session:
            if client_configuration(origin).get("aws_cognito_user_pool_id"):
                cls = CognitoSession
            else:
                cls = OpenIDSession
        return super().__new__(cls) # pyright: ignore[reportArgumentType]

    def authenticate_with_password(self, username: str, password: str) -> None:
        raise NotImplementedError

    def authenticate_with_browser(self) -> None:
        raise NotImplementedError

    def renew_tokens(self, *, refresh_token: Optional[str]) -> None:
        raise NotImplementedError

    def verify_tokens(self, *, id_token: Optional[str], access_token: Optional[str], refresh_token: Optional[str]) -> None:
        raise NotImplementedError

    @property
    def id_token(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def access_token(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def refresh_token(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def id_claims(self) -> Optional[Mapping[str, Any]]:
        raise NotImplementedError


class OpenIDSession(Session):
    """
    Authentication session interface for OpenID.

    The interface of this class aims to be hard or impossible to accidentally
    use insecurely.
    """
    def __init__(self, origin: Origin):
        assert origin
        self.origin = origin

        self.openid_configuration = openid_configuration(origin)
        self.client_configuration = client_configuration(origin)

        self.jwks = jwt.PyJWKClient(self.openid_configuration["jwks_uri"])

        self.can_authenticate_with_browser = "code" in self.client_configuration.get("response_types", [])
        self.can_authenticate_with_password = False

        self._tokens: Dict[str, Optional[str]] = {}
        self._claims: Dict[str, Dict[str, Any]] = {}

    @property
    def id_token(self):
        """
        The id token for this session, set by calling
        :meth:`.authenticate_with_password`,
        :meth:`.authenticate_with_browser`, or :meth:`.verify_tokens`.

        Useful for persisting in external storage, but should be treated as an
        opaque value.  The claims embedded in this token are accessible in
        :attr:`.id_claims`.
        """
        return self._tokens.get("id")

    @property
    def access_token(self):
        """
        The access token for this session, set by calling
        :meth:`.authenticate_with_password`,
        :meth:`.authenticate_with_browser`, or :meth:`.verify_tokens`.

        Useful for persisting in external storage, but should be treated as an
        opaque value.
        """
        return self._tokens.get("access")

    @property
    def refresh_token(self):
        """
        The refresh token for this session, set by calling
        :meth:`.authenticate_with_password`,
        :meth:`.authenticate_with_browser`, or :meth:`.verify_tokens`.

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


    def authenticate_with_password(self, username: str, password: str) -> None:
        """
        Authenticates the given *username* and *password* with the IdP.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises an :exc:`IdPError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        # This could implement OAuth2's "password" grant type¹, but Cognito
        # doesn't support it² and we don't need to support it for other IdPs.
        #   -trs, 17 Nov 2023
        #
        # ¹ <https://datatracker.ietf.org/doc/html/rfc6749#section-4.3>
        # ² Cognito supports password auth via its own API instead; see
        #   CognitoSession below.
        raise NotImplementedError


    def authenticate_with_browser(self) -> None:
        """
        Authenticates with the IdP via the user's web browser.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises an :exc:`IdPError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        # What follows is a basic implementation of the OpenID Connect (OIDC)¹
        # and OAuth 2.0² authorization code flow additionally secured with
        # Proof Key for Code Exchange (PKCE)³ and informed by the best current
        # practices for OAuth 2.0 native apps.⁴  Variable names and such
        # intentionally stick to the terms used in the specs to ease
        # understanding.  A survey of OIDC/OAuth2 libraries found nothing
        # suitable for our uses here.
        #   -trs, 17 Nov 2023
        #
        # ¹ <https://openid.net/specs/openid-connect-core-1_0.html>
        # ² <https://datatracker.ietf.org/doc/html/rfc6749>
        # ³ <https://datatracker.ietf.org/doc/html/rfc7636>
        # ⁴ <https://datatracker.ietf.org/doc/html/rfc8252>
        assert self.can_authenticate_with_browser


        # XXX TODO: This giant function should likely be broken up into
        # smaller, more digestable parts.  But I am out of time and cannot do
        # that now.  It works as-is and since it's only about internal
        # organization, I think fine to ship like this and fix it up later.  Of
        # course, fine for someone else to clean it up too!
        #   -trs, 21 Nov 2023


        # Set up a minimal HTTP server to receive the authorization response,
        # which contains query parameters we need to complete authentication.
        class AuthorizationResponseHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                assert isinstance(self.server, AuthorizationResponseServer)

                url = URL(self.path)

                if url.path.lstrip("/") == self.server.redirect_uri.path.lstrip("/"):
                    # Capture the HTTP request URL so we can parse the
                    # authorization response details (code, state, etc) later.
                    self.server.response_url = url
                    self.respond(200, "You may now close this page and return to the terminal.")
                else:
                    self.respond(400, "(Redirect path does not match expectation.)")

                # Accept only one request; close this request's connection and
                # stop the server.
                #
                # Shutting down the server from within a request handler only
                # works because we're using a ThreadingHTTPServer so we're
                # requesting shutdown from a different thread than the server.
                # With a non-threading HTTPServer, we'd deadlock here.
                self.close_connection = True
                self.server.shutdown()

            def respond(self, status: int, details: str):
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                css = """
                    body {
                      margin-top: 2rem;
                      text-align: center;
                      font-family: monospace;
                      font-size: 1.5rem;
                    }
                    h1 {
                      font-size: 2rem;
                      font-weight: normal;
                      background: black;
                      color: white;
                      background: linear-gradient(to right, #4377cd, #5097ba, #63ac9a, #7cb879, #9abe5c, #b9bc4a, #d4b13f, #e49938, #e67030, #de3c26);
                    }
                    .success { color: green }
                    .failure { color: red }
                    aside { font-size: 1rem }
                    """
                html = f"""
                    <style>{css}</style>
                    <h1>Nextstrain CLI</h1>
                    <p class="{'success' if status == 200 else 'failure'}">
                      Authentication {'complete' if status == 200 else 'failed'}.
                    <aside><p>{details}
                    """
                self.wfile.write(html.encode("utf-8"))

            def log_request(self, code = None, size = None):
                # Override default logging which clutters/obscures our own messages.
                pass


        class AuthorizationResponseServer(ThreadingHTTPServer):
            # Disable address and port reuse so other applications can't bind
            # to the same ones and intercept the response, per RFC 8252 § B.5.¹
            # The base http.server.ThreadingHTTPServer class allows reuse by
            # default, so we disable it.
            #   -trs, 20 Nov 2023
            #
            # ¹ <https://datatracker.ietf.org/doc/html/rfc8252#appendix-B.5>
            allow_reuse_address = False
            allow_reuse_port = False        # only present since Python ≥3.11

            # The URL we're listening at to accept the redirect from the
            # authorization server (IdP).
            redirect_uri: URL

            # The response URL from the authorization server (IdP) is captured
            # in this attribute to be used by code outside the server.
            response_url: Optional[URL] = None

            # Configure our corresponding fixed request handler and disable
            # default "bind_and_activate" behaviour in favor of automatic
            # binding *without* activation.  Binding lets us claim the socket
            # but we wait to accept requests on it until we're ready.
            def __init__(self, redirect_uri):
                super().__init__((redirect_uri.hostname, redirect_uri.port or 0), AuthorizationResponseHandler, bind_and_activate = False)
                self.redirect_uri = redirect_uri
                try:
                    self.server_bind()
                except:
                    self.server_close()
                    raise

            # Start listening on the bound socket when we enter a with block.
            # When we exit the block, the default behaviour is to stop
            # listening and close the socket.
            def __enter__(self):
                self.server_activate()
                return self


        # Pick a redirect URI from the list in the client configuration at
        # random and bind our server to a socket to claim it.  We don't start
        # listening on that socket until later, however.
        redirect_uris = set(map(URL, self.client_configuration.get("redirect_uris", [])))
        redirect_uri = None
        auth_response_server = None

        while redirect_uris and not auth_response_server:
            # Random choice without replacement
            redirect_uri = secrets.choice(list(redirect_uris))
            redirect_uris.remove(redirect_uri)

            # Redirect URI must be localhost/loopback IP and http://
            if not is_loopback(redirect_uri.hostname):
                debug(f"Skipping non-localhost/loopback redirect URI: {redirect_uri}")
                continue
            assert redirect_uri.scheme == "http"
            assert redirect_uri.hostname

            debug(f"Trying to bind socket for redirect URI: {redirect_uri}")

            try:
                auth_response_server = AuthorizationResponseServer(redirect_uri)
            except OSError as e:
                if e.errno == EADDRINUSE:
                    debug(f"Failed to bind to {redirect_uri.netloc} (EADDRINUSE); trying another redirect URI ({len(redirect_uris)} left)")
                    continue
                else:
                    raise

            # We let the OS pick an ephemeral port for us, so update
            # redirect_uri to include the port we got.
            if not redirect_uri.port:
                redirect_uri = redirect_uri._replace(
                    netloc = redirect_uri.hostname + ":" + str(auth_response_server.server_address[1]))
                debug(f"Updated redirect URI with ephemeral port: {redirect_uri}")


        if not auth_response_server:
            raise UserError(f"""
                Unable to listen on any local sockets to receive the
                authentication response.

                Retrying may help if the problem happens to be transient, or
                there might be a bug somewhere that needs to be fixed.

                If retrying after a bit doesn't help, please open a new issue
                at <https://github.com/nextstrain/cli/issues/new/choose> and
                include the complete output above and the command you were
                running.
                """)

        assert auth_response_server
        assert redirect_uri


        # For "state", Node's passport-oauth2, as we use it on nextstrain.org,
        # uses a 24-byte (192-bit) random value.¹  The OAuth2 RFC states only
        # that it must be "non-guessable"² and lays out some parameters for
        # what that means.³  A 32-byte (256-bit) random value seems good
        # enough.
        #
        # For "code_verifier", Node's passport-oauth2 uses a 32-byte (256-bit)
        # random value.⁴  The PKCE RFC states that it should be "impractical to
        # guess" and recommends 32 bytes.⁵  Sold.
        #   -trs, 21 Nov 2023
        #
        # ¹ <https://github.com/jaredhanson/passport-oauth2/blob/ea9e99ad/lib/state/pkcesession.js#L43>
        # ² <https://datatracker.ietf.org/doc/html/rfc6749#section-10.12>
        # ³ <https://datatracker.ietf.org/doc/html/rfc6749#section-10.10>
        # ⁴ <https://github.com/jaredhanson/passport-oauth2/blob/ea9e99ad/lib/strategy.js#L239>
        # ⁵ <https://datatracker.ietf.org/doc/html/rfc7636#section-4.1>
        state = base64url(secrets.token_bytes(32))
        code_verifier = base64url(secrets.token_bytes(32))

        auth_endpoint = URL(self.openid_configuration["authorization_endpoint"])
        auth_params = {
            "client_id": self.client_configuration["client_id"],
            "response_type": "code",
            "redirect_uri": str(redirect_uri),
            "scope": " ".join(self._requested_scopes()),
            "state": state,
            "code_challenge": base64url(sha256(code_verifier).digest()),
            "code_challenge_method": "S256" }

        # Per <https://datatracker.ietf.org/doc/html/rfc6749#section-3.1>:
        #
        # The endpoint URI MAY include an "application/x-www-form-urlencoded"
        # formatted […] query component […], which MUST be retained when
        # adding additional query parameters.
        auth_url = auth_endpoint._replace(query = auth_endpoint.query + (auth_endpoint.query and "&") + query(auth_params))
        assert auth_url.scheme == "https"


        # All preparations are in order!  We're ready to start the server that
        # will receive the authentication response and prompt the user to
        # authenticate via their web browser.
        with auth_response_server:
            server_thread = Thread(target = auth_response_server.serve_forever, daemon = True)
            server_thread.start()

            print("Automatically opening" if BROWSER else "Please visit", "the following URL in your web browser:")
            print()
            print(f"  {auth_url}")
            print()
            print(fill(cleandoc(f"""
                Aftering logging in via your web browser, you should see an
                "Authentication complete" page and can then return here to the
                terminal.
                """)))
            print()

            # Prepare for trouble.  Our server on localhost may not be
            # reachable if we, Nextstrain CLI, are running on a different
            # computer than the user's web browser, e.g. if the user is running
            # `nextstrain` on a remote server via SSH.  Give them a way to
            # workaround that issue, even if it's a bit janky and involves
            # copy/pasting.  We can improve it later.
            #   -trs, 21 Nov 2023
            input_url = None

            def input_reader():
                nonlocal input_url
                print(fill(cleandoc(f"""
                    Having trouble?  If you see an \"Unable to connect\" or
                    \"This site can't be reached\" error page after logging in
                    via your browser, try copying the URL in the address bar of
                    your browser — it'll begin with {redirect_uri} — and pasting
                    it below.
                    """)))
                print()
                while input_url is None:
                    try:
                        input_url = URL(input("URL: "))
                    except EOFError:
                        print(f"(eof; no input to read)")
                        break
                    if not str(input_url):
                        input_url = None

            input_thread = Thread(target = input_reader, daemon = True)
            input_thread.start()

            if BROWSER:
                open_browser(auth_url)

            # Block until one of the threads exits.
            while server_thread.is_alive() and input_thread.is_alive():
                server_thread.join(0.1)
                input_thread.join(0.1)

            if input_thread.is_alive():
                print("(nevermind!)")

                # XXX TODO: Ideally we'd stop/cancel the input thread here.
                # But we can't.  There's no simple cross-platform way to
                # interrupt input().  There are simple ways on Unix, but not
                # Windows.  And there are more complex, cross-platform ways
                # (e.g. trio).  Ignore this issue for now and don't worry about
                # it.  It's ok to let the thread hanging out there waiting for
                # input, as the entire process will be exiting soon anyway and
                # we'll ignore any input even if it does find some to read.
                # -trs, 21 Nov 2023

            if server_thread.is_alive():
                if not input_thread.is_alive() and input_url:
                    # We got a pasted input, so stop the server.
                    auth_response_server.shutdown()
                server_thread.join()

            print()


        # This URL contains the "code" and "state" query parameters we need to
        # complete authentication (or the "error" and related parameters if
        # something went wrong).
        auth_response_url = auth_response_server.response_url or input_url

        if not auth_response_url:
            raise UserError(f"""
                An error occurred while completing authentication.  The
                authorization response was not obtained.

                Retrying may help if the problem happens to be transient, or
                there might be a bug somewhere that needs to be fixed.

                If retrying after a bit doesn't help, please open a new issue
                at <https://github.com/nextstrain/cli/issues/new/choose> and
                include the complete output above and the command you were
                running.
                """)
        elif auth_response_url.query_fields.get("error"):
            # If the IdP sent us an error, not much we can do but display it and
            # let the user find someone to help them troubleshoot/debug.  The
            # relevant specs are:
            #
            #   OAuth2 <https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.2.1>
            #   OIDC <https://openid.net/specs/openid-connect-core-1_0.html#AuthError>
            #
            raise UserError(f"""
                An error occurred while completing authentication.  The
                authorization response was:

                   {auth_response_url}

                Retrying may help if the problem happens to be transient, or
                there might be a bug somewhere that needs to be fixed.

                If retrying after a bit doesn't help, please open a new issue
                at <https://github.com/nextstrain/cli/issues/new/choose> and
                include the complete output above and the command you were
                running.
                """)


        # Check the state we expect is the state we got back.
        assert secrets.compare_digest(state, auth_response_url.query_fields["state"][0].encode("ascii"))


        # Exchange the authorization code for the tokens, proving to the IdP
        # that we know the original code_verifier (thus completing the PKCE
        # protocol).
        code = auth_response_url.query_fields["code"][0]

        token_endpoint = URL(self.openid_configuration["token_endpoint"])
        assert token_endpoint.scheme == "https"

        response = requests.post(str(token_endpoint), {
            "client_id": self.client_configuration["client_id"],
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": str(redirect_uri) })

        result = response.json()

        # Convert anticipated errors from the OIDC/OAuth2 spec into a generic
        # error we handle.
        if response.status_code == 400:
            error = result.get("error") or "400 Bad Request"
            raise NotAuthorizedError(error)

        # Raise for other errors.
        response.raise_for_status()

        self.verify_tokens(
            id_token      = result.get("id_token"),
            access_token  = result.get("access_token"),
            refresh_token = result.get("refresh_token"))


    def _requested_scopes(self) -> Set[str]:
        required  = {"openid", "profile"}
        optional  = {"email", "offline_access"}
        supported = {*self.openid_configuration.get("scopes_supported", [])}
        missing   = required - supported

        assert not missing, f"IdP does not advertise support for the required scopes: {missing!r}"

        return required | (optional & supported)


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

        If unsuccessful, raises an :exc:`IdPError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        if not refresh_token:
            raise MissingTokenError("refresh")

        token_endpoint = URL(self.openid_configuration["token_endpoint"])
        assert token_endpoint.scheme == "https"

        response = requests.post(str(token_endpoint), {
            "client_id": self.client_configuration["client_id"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token })

        result = response.json()

        # Convert anticipated errors from the OIDC/OAuth2 spec into a generic
        # error we handle.
        if response.status_code == 400:
            error = result.get("error") or "400 Bad Request"
            raise NotAuthorizedError(error)

        # Raise for other errors.
        response.raise_for_status()

        self.verify_tokens(
            id_token      = result.get("id_token"),
            access_token  = result.get("access_token"),
            refresh_token = result.get("refresh_token", refresh_token))


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

        self._verify_id_token(id_token)
        self._tokens["access"] = access_token
        self._tokens["refresh"] = refresh_token


    def _verify_id_token(self, token):
        """
        Verifies all aspects of the given ID *token* (a signed JWT) except for the iat
        (issued at claim, see <https://github.com/nextstrain/cli/issues/307>)

        Assertions about expected algorithms, audience, issuer, and token use
        follow guidelines from
        <https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html>.

        See also <https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation>.
        """
        use = "id"
        jwk = self.jwks.get_signing_key_from_jwt(token)

        try:
            claims = jwt.decode(
                token,
                jwk.key,
                algorithms = ["RS256"],
                audience   = self.client_configuration["client_id"],
                issuer     = self.openid_configuration["issuer"],
                options    = { "require": ["exp"],
                               "verify_iat": False,
                             })

        except jwt.exceptions.ExpiredSignatureError:
            raise ExpiredTokenError(use)

        except jwt.exceptions.InvalidTokenError as e:
            raise TokenError(f"{type(e).__name__}: {str(e)}")

        # AWS Cognito includes the kind of token, id or access, in the claims for
        # each token itself, e.g. so if you're expecting id tokens you can verify
        # someone handed you an id token and not an access token.  This presumably
        # helps block token misuse attacks, e.g. when code that's expecting an id
        # token is given an access token that looks close enough in terms of claims
        # but ends up breaking unasserted expections of the code and allowing an
        # authz bypass or privilege escalation.
        #
        # There is not, AFAICT, a standard claim for this information in OIDC, and
        # other IdPs don't provide it, so we only check this claim if it exists.
        #   -trs, 11 Oct 2023 (copied from <https://github.com/nextstrain/nextstrain.org/blob/7ae36f54/src/authn/index.js#L658-L669>
        claimed_use = claims.get("token_use")

        if claimed_use is not None and claimed_use != use:
            raise InvalidUseError(f"{use} (expected) != {claimed_use} (claimed)")

        self._tokens[use] = token
        self._claims[use] = claims

        return claims


class CognitoSession(OpenIDSession):
    """
    Augments :class:`OpenIDSession` with username/password authentication
    capabilities using Cognito's support for the Secure Remote Password
    protocol.
    """
    def __init__(self, origin: Origin):
        super().__init__(origin)

        assert self.client_configuration.get("aws_cognito_user_pool_id")

        self.client_id        = self.client_configuration["client_id"]
        self.user_pool_id     = self.client_configuration["aws_cognito_user_pool_id"]
        self.user_pool_region = self.user_pool_id.split("_")[0]

        self.cognito = boto3.client("cognito-idp", region_name = self.user_pool_region)

        self.can_authenticate_with_password = True


    def authenticate_with_password(self, username: str, password: str) -> None:
        """
        Authenticates the given *username* and *password* with Cognito using
        the Secure Remote Password protocol.

        If successful, returns nothing, but several instance attributes will be
        set:

        * :attr:`.id_token`
        * :attr:`.access_token`
        * :attr:`.refresh_token`
        * :attr:`.id_claims`

        If unsuccessful, raises an :exc:`IdPError` or :exc:`TokenError` (or
        one of their subclasses).
        """
        assert self.can_authenticate_with_password

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


def base64url(data: bytes) -> bytes:
    """
    URL-safe Base64 encoding, without padding.
    <https://datatracker.ietf.org/doc/html/rfc7636#appendix-A>
    """
    urlsafe = bytes.maketrans(b"+/", b"-_")
    return b64encode(data).translate(urlsafe, delete = b"=")

.. highlight:: none

.. XXX FIXME
.. warning::
    This is a prospective document.  It details planned behaviour not the
    current behaviour.

    The currently implemented thing is the section at the very bottom.

    This whole document needs reworking.
      -trs, 21 Nov 2023


==============
Authentication
==============

Nextstrain CLI interacts with the same identity provider (IdP) as
nextstrain.org, using the same OpenID Connect 1.0 and OAuth 2.0 protocols, in
order to establish a user login and keep it updated.  The associated user
tokens obtained from the IdP are included by Nextstrain CLI in its requests to
nextstrain.org.

.. hint::
    If the diagrams below are too small, you can right click and choose "Open
    image in new tab" to see them full size.


.. _login flow:

Login flow
==========

The initial login flow is an adaptation of the standard `OpenID Connect 1.0
authorization code flow`_, which is itself built upon the `OAuth 2.0
authorization code flow`_.  See :ref:`comparison-to-the-standard` for how it
differs.

.. mermaid::

    sequenceDiagram
        actor user as User
        participant cli as Nextstrain CLI
        participant .org as nextstrain.org
        participant idp as IdP

        user->>cli: nextstrain login
        activate cli
        
            cli->>+.org: GET /.well-known/openid-configuration
            activate .org
                .org->>-cli: {authorization_endpoint, …}
            deactivate .org

            note over cli: generates authorization URL

            cli->>user: "Visit /authorize?state&code_challenge&…"
            note over cli: state and code_verifier <br> (used to derive code_challenge) <br> are stored in process memory

            user-->>idp: GET /authorize?state&code_challenge&…
            activate idp
                user-->>idp: Logs in
                idp-->>.org: Location: /cli/logged-in?code&state
            deactivate idp

            activate .org
                .org-->>user: "Confirm intent to log in to the CLI and that it's presenting {state}"
                user-->>.org: confirms (or denies)
                note over .org: stores code <br> keyed by state <br> with very short TTL <br> (or discards)
                .org-->>user: "Login complete, return to the terminal."
            deactivate .org

            cli->>.org: GET /cli/login/{state}
            activate .org
                note over cli,.org: polling
                note over .org: deletes code <br> keyed by state
                .org->>cli: {code}
            deactivate .org

            cli->>idp: GET /tokens?code&code_verifier&…
            activate idp
                idp->>cli: {id_token, access_token, refresh_token}
            deactivate idp

            note over cli: stores in <br> ~/.nextstrain/secrets

            cli->>user: success
        deactivate cli

A usability downside here is that the authorization URL the user must visit is
very long.  However, this can be mitigated in many cases by automatically
opening the URL in the browser.


.. _renewal flow:

Renewal flow
============

.. mermaid::

    sequenceDiagram
        actor user as User
        participant cli as Nextstrain CLI
        participant .org as nextstrain.org
        participant idp as IdP

        user->>cli: nextstrain login --renew <br> (explicit or implicit)
        activate cli

            cli->>.org: GET /.well-known/openid-configuration
            activate .org
                .org->>cli: {token_endpoint, …}
            deactivate .org

            note over cli: generates renewal URL

            cli->>idp: POST /tokens?grant_type=refresh_token&…
            activate idp
                idp->>cli: {id_token, access_token, refresh_token}
            deactivate idp

            note over cli: stores in <br> ~/.nextstrain/secrets

            cli->>user: success

        deactivate cli


.. _comparison-to-the-standard:

Comparison to the standard
==========================

The standard `OAuth 2.0 authorization code flow`_ involves four different
entities, dubbed the

1. *Resource Owner*, i.e. user of Nextstrain CLI
2. *User-Agent*, i.e. the user's web browser
3. *Client*, i.e. Nextstrain CLI
4. *Authorization Server*, i.e. the IdP in use (e.g. AWS Cognito)

The flow between these entities looks like this, as diagrammed in the RFC::

    +----------+
    | Resource |
    |   Owner  |
    |          |
    +----------+
         ^
         |
        (B)
    +----|-----+          Client Identifier      +---------------+
    |         -+----(A)-- & Redirection URI ---->|               |
    |  User-   |                                 | Authorization |
    |  Agent  -+----(B)-- User authenticates --->|     Server    |
    |          |                                 |               |
    |         -+----(C)-- Authorization Code ---<|               |
    +-|----|---+                                 +---------------+
      |    |                                         ^      v
     (A)  (C)                                        |      |
      |    |                                         |      |
      ^    v                                         |      |
    +---------+                                      |      |
    |         |>---(D)-- Authorization Code ---------'      |
    |  Client |          & Redirection URI                  |
    |         |                                             |
    |         |<---(E)----- Access Token -------------------'
    +---------+       (w/ Optional Refresh Token)

    Note: The lines illustrating steps (A), (B), and (C) are broken
    into two parts as they pass through the user-agent.

Nextstrain CLI's adapted `login flow`_ differs in a key aspect from this
standard diagram: step *(C)* passes thru nextstrain.org between the
*User-Agent* and *Client*::

    〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰
    |         -+----(A)-- & Redirection URI ---->|               |
    |  User-   |                                 | Authorization |
    |  Agent  -+----(B)-- User authenticates --->|     Server    |
    |          |                                 |               |
    |         -+----(C)-- Authorization Code ---<|               |
    +-|----|---+                                 +---------------+
      |    |                                         ^      v
      |   (C)                                        |      |
      |    |                                         |      |
      | +----------------+                           |      |
      | | nextstrain.org |                           |      |
      | +----------------+                           |      |
      |    |                                         |      |
     (A)   |                                         |      |
      |    |                                         |      |
      ^    v                                         |      |
    +---------+                                      |      |
    |         |>---(D)-- Authorization Code ---------'      |
    |  Client |          & Redirection URI                  |
    |         |                                             |
    〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰〰

Conceptually, nextstrain.org serves here as a "Client-Agent" in a sense or a
"Client-Proxy": it receives the authorization code, stores it in escrow, and
then makes it available to Nextstrain CLI upon a backchannel request.  This is
necessary to avoid:

 1. Nextstrain CLI running a web server on localhost in order to receive the
    authorization code directly.  While this is generally preferrable, it is
    not possible when Nextstrain CLI is running on a host different than the
    user's web browser (e.g. when running ``nextstrain`` over SSH).

 2. A manual step of the user copying and pasting a long opaque string
    (containing the authorization code and state) into a prompt provided by
    Nextstrain CLI.

This adaptation was informed by the `OAuth 2.0 device authorization flow`_.  In
some sense, the adapted flow is a device-like flow "bolted on" to the
authorization code flow.  If AWS Cognito supported the device flow, we would
likely be using it, with Nextstrain CLI acting as the "device".

Security
--------

The interposition of nextstrain.org has a crucial implication, however:
Nextstrain CLI (the *Client*) doesn't have a way to bind the web browser (the
*User-Agent*) used to complete most of the flow.  For example, in a web context
when nextstrain.org is the *Client*, session cookies (secure, origin-bound) let
the *Client* know that the *User-Agent* it sent to the IdP to authenticate is
the same *User-Agent* that's returned from the IdP bearing an authorization
code.  In contrast, in this CLI context, the *User-Agent* doesn't directly
return to the *Client*.

This means that our adapted flow has the same `remote phishing`_ security
considerations as the standard device authorization flow.


Alternatives
============

Nextstrain CLI doesn't talk to IdP in login flow
------------------------------------------------

Early brainstorming suggested an alternative to the `login flow`_ where
Nextstrain CLI doesn't construct an authorization URL itself but instead
directs the user to visit nextstrain.org (e.g. at ``/cli/login``) where
nextstrain.org then completes a standard authorization code flow with the
user-agent and IdP before returning the tokens themselves to Nextstrain CLI
(which has been polling for them).  Similar to the `OAuth 2.0 device
authorization flow`_ but with differences because it'd be conducted completely
outside the framework of OAuth 2.0.

.. mermaid::

    sequenceDiagram
        actor user as User
        participant cli as Nextstrain CLI
        participant .org as nextstrain.org
        participant idp as IdP

        user->>cli: nextstrain login
        activate cli

        note over cli: generates {uuid} (v4)

        cli->>user: "Visit /cli/login/{uuid}"
        user-->>.org: GET /cli/login/{uuid}
        activate .org
        note over .org: stores {uuid} in session
        .org-->>idp: Location: /authorize?state&code_challenge&…
        deactivate .org

        activate idp
        user-->>idp: Logs in
        idp-->>.org: Location: /cli/logged-in?code&state
        deactivate idp

        activate .org
        .org-->>user: "Confirm intent to log in to the CLI"
        user-->>.org: confirms (or denies)
        note over .org: exchanges code for tokens <br> stores them <br> keyed by uuid <br> (or discards)
        .org-->>user: "Login complete, return to the terminal."
        deactivate .org

        cli->>.org: GET /cli/logged-in/{uuid}
        activate .org
        note over cli,.org: polling
        note over .org: deletes tokens <br> keyed by uuid
        .org->>cli: {id_token, access_token, refresh_token}
        deactivate .org

        cli->>user: success
        deactivate cli

This was rejected because Nextstrain CLI still needs to perform OAuth 2.0 token
exchanges with the IdP directly for the `renewal flow`_, so it seemed
advantageous to move closer towards OAuth 2.0 rather than away from it.  It
also requires fetching and temporarily storing the tokens on nextstrain.org.


nextstrain.org implements device authorization-like flow
--------------------------------------------------------

While Cognito doesn't implement device authorization flow, we could implement a
very similar flow on nextstrain.org ourselves, slightly tailored for the CLI
and the circumstances of building it on top of the IdP instead as part of the
IdP::

    GET /.well-known/openid-configuration
    {
        …,
        cli_authorization_endpoint: "…/cli/login",  // akin to device_authorization_endpoint
        cli_token_endpoint: "…/cli/tokens",         // akin to token_endpoint
        …
    }

    POST /cli/login {client_id}&{scope}     [stores (client_id, cli_code) with a short TTL keyed by user_code,
    {                                        stores {"error":"authorization_pending"} with a short TTL keyed by cli_code]
      cli_code: "long string",
      user_code: "short string",
      verification_uri: "…/cli/login",
      verification_uri_complete: "…/cli/login/{user_code}",
      …
    }

        +--------------------------------------------------+
        |                                                  |
        |  Open the following link:                        |
        |    https://nextstrain.org/cli/login/{user_code}  |
        |                                                  |
        |  or on another device visit:                     |
        |    https://nextstrain.org/cli/login              |
        |                                                  |
        |  and enter the code:                             |
        |    WDJB-MJHT                                     |
        |                                                  |
        +--------------------------------------------------+

        GET /cli/login/{user_code}          [stores user_code in session]
        Location: …/oauth2/authorize?…

        [user logs in]
        Location: https://nextstrain.org/cli/logged-in?code&state

        GET /cli/logged-in?code&state

        "Confirm intent to log in to the CLI and that it is presenting {user_code}."
        "Yes/No"

        POST /cli/logged-in code&state&confirmed

        [verifies state,
         exchanges code (with PKCE) for tokens,
         looks up and deletes (client_id, cli_code) by the user_code in session,
         stores tokens with a short TTL keyed by (client_id, cli_code),
         tokens encrypted with (client_id, cli_code) as context,
         (or if denied, deletes user_code from session, stores {"error":"access_denied"} keyed by (client_id, cli_code))]


    POST /cli/tokens {cli_code}&{client_id}             [looks up and deletes tokens with (client_id, cli_code)]
    {id_token, access_token, refresh_token, scope}

    [(if lookup fails, then return {"error":"expired_token"})]

The main difference between this alternative and the chosen `login flow`_ is
that here the tokens must be fetched and temporarily stored on the server
instead of solely by Nextstrain CLI.  That's significant complication.

But maybe this flow overall is easier to describe and explain since it's much
more similar to the standard device authorization flow?


Nextstrain CLI does standard authorization code flow
----------------------------------------------------

Nextstrain CLI is definitely software, an "app", that runs "natively" on a
user's computer, a "device".  It's not a device itself.  However, it's needs
sit somewhere between the `OAuth 2.0 device authorization flow`_ and the `OAuth
2.0 for native apps`_ best current practice:

 1. Often, like apps, login flows can go thru a user-agent, a web browser, on
    the same computer.  This means listening on localhost and doing standard
    authorization code flows works.

 2. Sometimes however, like devices, login flows must happen on a user-agent on
    a different device.  This means listening on localhost and doing standard
    authorization code flows does not work.

Given two conflicting requirements that can't use the same flow, the thought
was to cater to the least capable (or most restricted) situation (2).  An app
can act like a device, but a device cannot act like an app, so make all
situations device-like.  At least that's how the thinking went.

However, maybe we can act like an app instead and provide the user an
acceptable workaround for when we're device-like.  The possibility of this
workaround was a recent realization.

When Nextstrain CLI is running on a different computer than the user-agent, the
redirection back to localhost will (very likely) fail, showing some "unable to
connect to server" page in the browser.  If this happens, users can copy and
paste the URL from the address bar and curl it from the same computer running
Nextstrain CLI.  Alternatively, Nextstrain CLI could directly accept the URL as
pasted input.  We can improve this situation in the future if it warrants it.

One final niggle.  The best practices on `loopback interface redirection`_
state:

    The authorization server MUST allow any port to be specified at the time of
    the request for loopback IP redirect URIs, to accommodate clients that
    obtain an available ephemeral port from the operating system at the time of
    the request.

but it turns out that AWS Cognito doesn't follow this and still requires an
exact port match.  Bummer.  I thought this was game over, but then I realized a
workaround: we can register a fixed list of dozens of ports and then have
Nextstrain CLI pick from that same fixed list rather than be truly random.  As
long as one port on the list is able to be bound to, it all works out.  Cognito
limits clients to 100 callback URLs, but that should be plenty.


.. _OpenID Connect 1.0 authorization code flow: https://openid.net/specs/openid-connect-core-1_0.html#CodeFlowAuth
.. _OAuth 2.0 authorization code flow: https://datatracker.ietf.org/doc/html/rfc6749#section-4.1
.. _OAuth 2.0 device authorization flow: https://datatracker.ietf.org/doc/html/rfc8628
.. _OAuth 2.0 for native apps: https://datatracker.ietf.org/doc/html/rfc8252
.. _loopback interface redirection: https://datatracker.ietf.org/doc/html/rfc8252#section-7.3
.. _remote phishing: https://datatracker.ietf.org/doc/html/rfc8628#section-5.4

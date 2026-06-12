def pytest_cognito_authn_ignores_aws_login_session(tmp_path, monkeypatch):
    """
    Ensure Cognito authn doesn't consult local AWS credentials.

    <https://github.com/nextstrain/cli/issues/533>
    """
    isolate_aws_credentials(tmp_path, monkeypatch)

    aws_config = tmp_path / "aws-config"
    aws_config.write_text(
        "\n".join([
            "[default]",
            "login_session = arn:aws:iam::123456789012:user/test",
            "",
        ])
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(aws_config))

    session = use_cognito_authn(monkeypatch)
    session.Session("https://nextstrain.org")


def isolate_aws_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "aws-credentials"))

    for name in [
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]:
        monkeypatch.delenv(name, raising = False)


def use_cognito_authn(monkeypatch):
    from nextstrain.cli.authn import session

    config = {
        "issuer": "https://example.com",
        "jwks_uri": "https://example.com/.well-known/jwks.json",
        "scopes_supported": ["openid", "profile"],
        "nextstrain_cli_client_configuration": {
            "client_id": "unused",
            "aws_cognito_user_pool_id": "us-east-1_unused",
        },
    }

    monkeypatch.setattr(session, "openid_configuration", lambda origin: config)
    monkeypatch.setattr(
        session,
        "client_configuration",
        lambda origin: config["nextstrain_cli_client_configuration"])

    return session

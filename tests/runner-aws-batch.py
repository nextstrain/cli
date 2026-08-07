import botocore.exceptions
import pytest
from nextstrain.cli.errors import UserError
from nextstrain.cli.runner.aws_batch import run
from unittest.mock import MagicMock, patch


def pytest_connection_error_on_attach():
    opts = MagicMock(attach="12345678-9abc-def0-1234-56789abcdef0", volumes=[])
    err = botocore.exceptions.EndpointConnectionError(endpoint_url="https://batch.us-east-1.amazonaws.com")

    with patch("nextstrain.cli.runner.aws_batch.jobs.lookup", side_effect=err):
        with pytest.raises(UserError) as exc_info:
            run(opts, [])

        assert "Lost connection with AWS Batch" in str(exc_info.value)
        assert "--attach 12345678-9abc-def0-1234-56789abcdef0" in str(exc_info.value)


def pytest_connection_error_on_update():
    opts = MagicMock(attach="12345678-9abc-def0-1234-56789abcdef0", volumes=[])
    mock_job = MagicMock(id="12345678-9abc-def0-1234-56789abcdef0", workdir="s3://bucket/dir")
    err = botocore.exceptions.EndpointConnectionError(endpoint_url="https://batch.us-east-1.amazonaws.com")
    mock_job.update.side_effect = err

    with patch("nextstrain.cli.runner.aws_batch.jobs.lookup", return_value=mock_job):
        with pytest.raises(UserError) as exc_info:
            run(opts, [])

        assert "Lost connection with AWS Batch" in str(exc_info.value)
        assert "--attach 12345678-9abc-def0-1234-56789abcdef0" in str(exc_info.value)

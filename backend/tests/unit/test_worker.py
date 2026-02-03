"""Unit tests for the worker handler."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestWorkerHandler:
    """Tests for worker Lambda handler."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with WebSocket endpoint configured."""
        with patch("api.handlers.worker.settings") as mock:
            mock.websocket_endpoint = "wss://test.execute-api.us-east-1.amazonaws.com/prod"
            mock.aws_region = "us-east-1"
            yield mock

    @pytest.fixture
    def mock_api_client(self):
        """Mock API Gateway Management client."""
        with patch("api.handlers.worker.get_api_gateway_management_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_handler_processes_job_successfully(self, mock_settings, mock_api_client):
        """Test successful job processing."""
        from api.handlers.worker import handler

        job = {
            "job_id": "test-job-123",
            "user_id": "user-456",
            "connection_id": "conn-789",
            "code": 'print("hello")',
            "timeout_seconds": 10.0,
        }

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(job),
                }
            ]
        }

        result = handler(event, None)

        assert result["batchItemFailures"] == []
        mock_api_client.post_to_connection.assert_called_once()

        # Verify the message sent to WebSocket
        call_args = mock_api_client.post_to_connection.call_args
        assert call_args[1]["ConnectionId"] == "conn-789"
        sent_data = json.loads(call_args[1]["Data"].decode("utf-8"))
        assert sent_data["type"] == "execution_result"
        assert sent_data["job_id"] == "test-job-123"
        assert sent_data["success"] is True
        assert "hello" in sent_data["stdout"]

    def test_handler_fails_without_websocket_endpoint(self):
        """Test handler fails when WebSocket endpoint not configured."""
        from api.handlers.worker import handler

        with patch("api.handlers.worker.settings") as mock:
            mock.websocket_endpoint = ""

            event = {
                "Records": [
                    {
                        "messageId": "msg-1",
                        "body": json.dumps({"job_id": "test"}),
                    }
                ]
            }

            result = handler(event, None)

            # All records should fail
            assert len(result["batchItemFailures"]) == 1
            assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-1"

    def test_handler_handles_gone_connection(self, mock_settings, mock_api_client):
        """Test handler handles disconnected WebSocket connections."""
        from botocore.exceptions import ClientError

        from api.handlers.worker import handler

        # Simulate connection gone
        mock_api_client.post_to_connection.side_effect = ClientError(
            {"Error": {"Code": "GoneException", "Message": "Connection gone"}},
            "PostToConnection",
        )

        job = {
            "job_id": "test-job-123",
            "connection_id": "conn-gone",
            "code": 'print("hello")',
        }

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(job),
                }
            ]
        }

        result = handler(event, None)

        # Should not fail (connection just gone)
        assert result["batchItemFailures"] == []

    def test_handler_handles_invalid_json(self, mock_settings, mock_api_client):
        """Test handler handles malformed JSON messages."""
        from api.handlers.worker import handler

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": "not valid json {{{",
                }
            ]
        }

        result = handler(event, None)

        # Should not retry invalid JSON
        assert result["batchItemFailures"] == []

    def test_handler_handles_missing_connection_id(self, mock_settings, mock_api_client):
        """Test handler handles jobs without connection_id."""
        from api.handlers.worker import handler

        job = {
            "job_id": "test-job-123",
            "code": 'print("hello")',
            # Missing connection_id
        }

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(job),
                }
            ]
        }

        result = handler(event, None)

        # Should not retry - invalid message
        assert result["batchItemFailures"] == []
        mock_api_client.post_to_connection.assert_not_called()

    def test_handler_captures_execution_errors(self, mock_settings, mock_api_client):
        """Test handler captures and reports execution errors."""
        from api.handlers.worker import handler

        job = {
            "job_id": "test-job-123",
            "connection_id": "conn-789",
            "code": "x = 1 / 0",  # ZeroDivisionError
        }

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(job),
                }
            ]
        }

        result = handler(event, None)

        assert result["batchItemFailures"] == []
        mock_api_client.post_to_connection.assert_called_once()

        call_args = mock_api_client.post_to_connection.call_args
        sent_data = json.loads(call_args[1]["Data"].decode("utf-8"))
        assert sent_data["success"] is False
        assert sent_data["error_type"] == "ZeroDivisionError"

    def test_handler_handles_security_violations(self, mock_settings, mock_api_client):
        """Test handler handles code with security violations."""
        from api.handlers.worker import handler

        job = {
            "job_id": "test-job-123",
            "connection_id": "conn-789",
            "code": "import os",  # Blocked import
        }

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(job),
                }
            ]
        }

        result = handler(event, None)

        assert result["batchItemFailures"] == []

        call_args = mock_api_client.post_to_connection.call_args
        sent_data = json.loads(call_args[1]["Data"].decode("utf-8"))
        assert sent_data["success"] is False
        assert sent_data["error_type"] == "SecurityError"
        assert len(sent_data["security_violations"]) > 0


class TestSendToConnection:
    """Tests for send_to_connection helper."""

    def test_send_to_connection_success(self):
        """Test successful message sending."""
        from api.handlers.worker import send_to_connection

        mock_client = MagicMock()
        result = send_to_connection(mock_client, "conn-123", {"type": "test", "data": "hello"})

        assert result is True
        mock_client.post_to_connection.assert_called_once()

    def test_send_to_connection_gone_exception(self):
        """Test handling of gone connection."""
        from botocore.exceptions import ClientError

        from api.handlers.worker import send_to_connection

        mock_client = MagicMock()
        mock_client.post_to_connection.side_effect = ClientError(
            {"Error": {"Code": "GoneException"}}, "PostToConnection"
        )

        result = send_to_connection(mock_client, "conn-123", {"type": "test"})

        assert result is False

    def test_send_to_connection_other_error_raises(self):
        """Test that other errors are re-raised."""
        from botocore.exceptions import ClientError

        from api.handlers.worker import send_to_connection

        mock_client = MagicMock()
        mock_client.post_to_connection.side_effect = ClientError(
            {"Error": {"Code": "InternalError"}}, "PostToConnection"
        )

        with pytest.raises(ClientError):
            send_to_connection(mock_client, "conn-123", {"type": "test"})

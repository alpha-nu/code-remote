"""Unit tests for the sync service."""

import json
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from botocore.exceptions import ClientError


class TestSyncService:
    """Tests for SyncService."""

    @pytest.fixture
    def mock_sqs_client(self):
        """Create a mock SQS client."""
        mock = MagicMock()
        mock.send_message.return_value = {"MessageId": "msg-123"}
        return mock

    @pytest.fixture
    def service(self, mock_sqs_client):
        """Create a SyncService with mocked SQS client."""
        from api.services.sync_service import SyncService

        return SyncService(
            sqs_client=mock_sqs_client,
            queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue.fifo",
        )

    @pytest.mark.asyncio
    async def test_enqueue_analyzed_event(self, service, mock_sqs_client):
        """Test enqueueing an analyzed event."""
        result = await service.enqueue_analyzed(
            snippet_id="550e8400-e29b-41d4-a716-446655440000",
            user_id="660e8400-e29b-41d4-a716-446655440001",
        )

        assert result == "msg-123"
        mock_sqs_client.send_message.assert_called_once()

        # Verify message content
        call_kwargs = mock_sqs_client.send_message.call_args[1]
        assert "test-queue.fifo" in call_kwargs["QueueUrl"]
        body = json.loads(call_kwargs["MessageBody"])
        assert body["event_type"] == "snippet.analyzed"
        assert body["snippet_id"] == "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_enqueue_deleted_event(self, service, mock_sqs_client):
        """Test enqueueing a deleted event."""
        result = await service.enqueue_deleted(
            snippet_id="550e8400-e29b-41d4-a716-446655440000",
            user_id="660e8400-e29b-41d4-a716-446655440001",
        )

        assert result == "msg-123"
        call_kwargs = mock_sqs_client.send_message.call_args[1]
        body = json.loads(call_kwargs["MessageBody"])
        assert body["event_type"] == "snippet.deleted"

    @pytest.mark.asyncio
    async def test_enqueue_event_uses_message_group_id(self, service, mock_sqs_client):
        """Test that events use snippet_id as MessageGroupId."""
        await service.enqueue_analyzed(
            snippet_id="550e8400-e29b-41d4-a716-446655440000",
            user_id="660e8400-e29b-41d4-a716-446655440001",
        )

        call_kwargs = mock_sqs_client.send_message.call_args[1]
        # MessageGroupId should be the snippet_id for FIFO ordering
        assert "MessageGroupId" in call_kwargs
        assert call_kwargs["MessageGroupId"] == "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_enqueue_event_returns_none_on_error(self, service, mock_sqs_client):
        """Test that SQS errors return None."""
        mock_sqs_client.send_message.side_effect = ClientError(
            {"Error": {"Code": "QueueDoesNotExist", "Message": "Queue not found"}},
            "SendMessage",
        )

        result = await service.enqueue_analyzed(
            snippet_id="550e8400-e29b-41d4-a716-446655440000",
            user_id="660e8400-e29b-41d4-a716-446655440001",
        )

        assert result is None


class TestSnippetSyncEvent:
    """Tests for SnippetSyncEvent schema."""

    def test_analyzed_factory(self):
        """Test the analyzed factory method."""
        from api.schemas.sync import SnippetSyncEvent

        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

        assert event.event_type == "snippet.analyzed"
        assert str(event.snippet_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert event.timestamp is not None

    def test_deleted_factory(self):
        """Test the deleted factory method."""
        from api.schemas.sync import SnippetSyncEvent

        event = SnippetSyncEvent.deleted(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

        assert event.event_type == "snippet.deleted"

    def test_to_sqs_message_format(self):
        """Test SQS message format."""
        from api.schemas.sync import SnippetSyncEvent

        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

        message = event.to_sqs_message()

        assert "MessageBody" in message
        assert "MessageGroupId" in message
        assert message["MessageGroupId"] == "550e8400-e29b-41d4-a716-446655440000"

        # MessageBody should be valid JSON
        body = json.loads(message["MessageBody"])
        assert body["event_type"] == "snippet.analyzed"
        assert "timestamp" in body

    def test_model_validate_from_sqs(self):
        """Test parsing event from SQS message body."""
        from api.schemas.sync import SnippetSyncEvent

        sqs_body = {
            "event_type": "snippet.analyzed",
            "snippet_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440001",
            "timestamp": "2026-02-05T10:30:00Z",
        }

        event = SnippetSyncEvent.model_validate(sqs_body)

        assert event.event_type == "snippet.analyzed"
        assert str(event.snippet_id) == "550e8400-e29b-41d4-a716-446655440000"


class TestGetSyncService:
    """Tests for get_sync_service factory."""

    @patch("api.services.sync_service.boto3")
    @patch("api.services.sync_service.settings")
    def test_get_sync_service_uses_settings(self, mock_settings, mock_boto3):
        """Test that get_sync_service uses settings for queue URL."""
        from api.services.sync_service import get_sqs_client, get_sync_service

        # Clear the lru_cache
        get_sqs_client.cache_clear()

        mock_settings.snippet_sync_queue_url = "https://sqs.test/queue.fifo"
        mock_boto3.client.return_value = MagicMock()

        service = get_sync_service()

        assert service._queue_url == "https://sqs.test/queue.fifo"

"""Unit tests for the sync worker handler."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from api.handlers.sync_worker import (
    process_analyzed_event,
    process_deleted_event,
    process_event,
)
from api.schemas.sync import SnippetSyncEvent


class MockSnippet:
    """Mock snippet for testing."""

    def __init__(
        self,
        id="550e8400-e29b-41d4-a716-446655440000",
        title="Test Snippet",
        description="A test snippet",
        code="def test(): pass",
        language="python",
        time_complexity="O(n)",
        space_complexity="O(1)",
        user_id="660e8400-e29b-41d4-a716-446655440001",
    ):
        self.id = UUID(id)
        self.title = title
        self.description = description
        self.code = code
        self.language = language
        self.time_complexity = time_complexity
        self.space_complexity = space_complexity
        self.user_id = UUID(user_id)


class MockUser:
    """Mock user for testing."""

    def __init__(
        self,
        id="660e8400-e29b-41d4-a716-446655440001",
        email="test@example.com",
    ):
        self.id = UUID(id)
        self.email = email


class TestProcessAnalyzedEvent:
    """Tests for process_analyzed_event."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j service."""
        mock = MagicMock()
        mock.upsert_snippet = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding(self):
        """Create a mock embedding service."""
        mock = MagicMock()
        mock.build_snippet_embedding_input.return_value = "embedding input text"
        mock.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        return mock

    @pytest.fixture
    def analyzed_event(self):
        """Create an analyzed event."""
        return SnippetSyncEvent.analyzed(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

    @pytest.mark.asyncio
    async def test_process_analyzed_success(self, mock_neo4j, mock_embedding, analyzed_event):
        """Test successful processing of analyzed event."""
        snippet = MockSnippet()
        user = MockUser()

        with patch("api.handlers.sync_worker.get_session_factory") as mock_factory:
            # Mock the database session factory
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first.return_value = (snippet, user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            result = await process_analyzed_event(analyzed_event, mock_neo4j, mock_embedding)

        assert result is True
        mock_embedding.build_snippet_embedding_input.assert_called_once()
        mock_embedding.generate_embedding.assert_called_once()
        mock_neo4j.upsert_snippet.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_analyzed_snippet_not_found(
        self, mock_neo4j, mock_embedding, analyzed_event
    ):
        """Test handling when snippet is not found in database."""
        with patch("api.handlers.sync_worker.get_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first.return_value = None  # Snippet not found
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            result = await process_analyzed_event(analyzed_event, mock_neo4j, mock_embedding)

        assert result is False
        mock_neo4j.upsert_snippet.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_analyzed_embedding_failure(
        self, mock_neo4j, mock_embedding, analyzed_event
    ):
        """Test handling when embedding generation fails."""
        snippet = MockSnippet()
        user = MockUser()
        mock_embedding.generate_embedding.return_value = None  # Embedding fails

        with patch("api.handlers.sync_worker.get_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first.return_value = (snippet, user)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            result = await process_analyzed_event(analyzed_event, mock_neo4j, mock_embedding)

        assert result is False
        mock_neo4j.upsert_snippet.assert_not_called()


class TestProcessDeletedEvent:
    """Tests for process_deleted_event."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j service."""
        mock = MagicMock()
        mock.delete_snippet = AsyncMock()
        return mock

    @pytest.fixture
    def deleted_event(self):
        """Create a deleted event."""
        return SnippetSyncEvent.deleted(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

    @pytest.mark.asyncio
    async def test_process_deleted_success(self, mock_neo4j, deleted_event):
        """Test successful processing of deleted event."""
        result = await process_deleted_event(deleted_event, mock_neo4j)

        assert result is True
        mock_neo4j.delete_snippet.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")


class TestProcessEvent:
    """Tests for the main process_event dispatcher."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j service."""
        mock = MagicMock()
        mock.upsert_snippet = AsyncMock()
        mock.delete_snippet = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding(self):
        """Create a mock embedding service."""
        mock = MagicMock()
        mock.build_snippet_embedding_input.return_value = "text"
        mock.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        return mock

    @pytest.mark.asyncio
    async def test_process_event_routes_analyzed(self, mock_neo4j, mock_embedding):
        """Test that analyzed events are routed correctly."""
        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

        with patch(
            "api.handlers.sync_worker.process_analyzed_event",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = True
            result = await process_event(event, mock_neo4j, mock_embedding)

        assert result is True
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_routes_deleted(self, mock_neo4j, mock_embedding):
        """Test that deleted events are routed correctly."""
        event = SnippetSyncEvent.deleted(
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        )

        with patch(
            "api.handlers.sync_worker.process_deleted_event",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = True
            result = await process_event(event, mock_neo4j, mock_embedding)

        assert result is True
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_handles_unknown_type(self, mock_neo4j, mock_embedding):
        """Test that unknown event types return False."""
        # Create an event with an invalid type (using model_construct to bypass validation)
        event = SnippetSyncEvent.model_construct(
            event_type="snippet.unknown",
            snippet_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            user_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
            timestamp="2026-02-05T10:30:00Z",
        )

        result = await process_event(event, mock_neo4j, mock_embedding)

        assert result is False


class TestLambdaHandler:
    """Tests for the Lambda handler function."""

    @pytest.fixture
    def sqs_event(self):
        """Create a mock SQS event."""
        return {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {
                            "event_type": "snippet.analyzed",
                            "snippet_id": "550e8400-e29b-41d4-a716-446655440000",
                            "user_id": "660e8400-e29b-41d4-a716-446655440001",
                            "timestamp": "2026-02-05T10:30:00Z",
                        }
                    ),
                },
                {
                    "messageId": "msg-2",
                    "body": json.dumps(
                        {
                            "event_type": "snippet.deleted",
                            "snippet_id": "550e8400-e29b-41d4-a716-446655440002",
                            "user_id": "660e8400-e29b-41d4-a716-446655440001",
                            "timestamp": "2026-02-05T10:31:00Z",
                        }
                    ),
                },
            ]
        }

    def test_handler_processes_batch(self, sqs_event):
        """Test that handler processes all records in batch."""
        with patch("api.handlers.sync_worker.get_neo4j_driver"):
            with patch("api.handlers.sync_worker.Neo4jService"):
                with patch("api.handlers.sync_worker.EmbeddingService"):
                    with patch(
                        "api.handlers.sync_worker.process_event",
                        new_callable=AsyncMock,
                    ) as mock_process:
                        mock_process.return_value = True

                        from api.handlers.sync_worker import handler

                        result = handler(sqs_event, None)

        # Should return empty batch item failures on success
        assert result["batchItemFailures"] == []

    def test_handler_reports_failed_items(self, sqs_event):
        """Test that handler reports failed items for retry."""
        with patch("api.handlers.sync_worker.get_neo4j_driver"):
            with patch("api.handlers.sync_worker.Neo4jService"):
                with patch("api.handlers.sync_worker.EmbeddingService"):
                    with patch(
                        "api.handlers.sync_worker.process_event",
                        new_callable=AsyncMock,
                    ) as mock_process:
                        # First succeeds, second fails
                        mock_process.side_effect = [True, False]

                        from api.handlers.sync_worker import handler

                        result = handler(sqs_event, None)

        # Second message should be reported as failed
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-2"

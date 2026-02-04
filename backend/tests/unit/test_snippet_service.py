"""Unit tests for snippet service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.models import Snippet
from api.services.snippet_service import SnippetService


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def snippet_service(mock_db):
    """Create a SnippetService with mock database."""
    return SnippetService(mock_db)


@pytest.fixture
def sample_snippet():
    """Create a sample snippet for testing."""
    snippet = Snippet(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        code="print('hello')",
        title="Test Snippet",
        language="python",
        description="A test snippet",
        execution_count=0,
        is_starred=False,
        time_complexity=None,
        space_complexity=None,
    )
    snippet.created_at = datetime.now(UTC)
    snippet.updated_at = datetime.now(UTC)
    return snippet


class TestSnippetServiceCreate:
    """Tests for SnippetService.create()."""

    async def test_create_snippet_basic(self, snippet_service, mock_db):
        """Test creating a basic snippet."""
        user_id = uuid.uuid4()
        code = "print('hello')"

        # Mock refresh to set the returned snippet's attributes
        async def mock_refresh(snippet):
            snippet.id = uuid.uuid4()
            snippet.created_at = datetime.now(UTC)
            snippet.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await snippet_service.create(user_id=user_id, code=code)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        assert result.code == code
        assert result.user_id == user_id
        assert result.language == "python"

    async def test_create_snippet_with_all_fields(self, snippet_service, mock_db):
        """Test creating a snippet with all optional fields."""
        user_id = uuid.uuid4()
        code = "import math\nprint(math.pi)"
        title = "Math Example"
        description = "Shows math module usage"

        async def mock_refresh(snippet):
            snippet.id = uuid.uuid4()
            snippet.created_at = datetime.now(UTC)
            snippet.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await snippet_service.create(
            user_id=user_id,
            code=code,
            title=title,
            language="python",
            description=description,
        )

        assert result.title == title
        assert result.description == description


class TestSnippetServiceGetById:
    """Tests for SnippetService.get_by_id()."""

    async def test_get_by_id_found(self, snippet_service, mock_db, sample_snippet):
        """Test getting a snippet that exists."""
        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snippet
        mock_db.execute.return_value = mock_result

        result = await snippet_service.get_by_id(sample_snippet.id)

        assert result == sample_snippet
        mock_db.execute.assert_called_once()

    async def test_get_by_id_not_found(self, snippet_service, mock_db):
        """Test getting a snippet that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await snippet_service.get_by_id(uuid.uuid4())

        assert result is None

    async def test_get_by_id_with_user_filter(self, snippet_service, mock_db, sample_snippet):
        """Test getting a snippet with user ID filter."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snippet
        mock_db.execute.return_value = mock_result

        result = await snippet_service.get_by_id(sample_snippet.id, user_id=sample_snippet.user_id)

        assert result == sample_snippet


class TestSnippetServiceListByUser:
    """Tests for SnippetService.list_by_user()."""

    async def test_list_by_user_empty(self, snippet_service, mock_db):
        """Test listing snippets when user has none."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await snippet_service.list_by_user(uuid.uuid4())

        assert result == []

    async def test_list_by_user_with_snippets(self, snippet_service, mock_db, sample_snippet):
        """Test listing snippets when user has some."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_snippet]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await snippet_service.list_by_user(sample_snippet.user_id)

        assert len(result) == 1
        assert result[0] == sample_snippet

    async def test_list_by_user_with_pagination(self, snippet_service, mock_db):
        """Test listing snippets with custom limit and offset."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        await snippet_service.list_by_user(uuid.uuid4(), limit=10, offset=5)

        mock_db.execute.assert_called_once()


class TestSnippetServiceListSummaries:
    """Tests for SnippetService.list_summaries_by_user()."""

    async def test_list_summaries_empty(self, snippet_service, mock_db):
        """Test listing summaries when user has none."""
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        result = await snippet_service.list_summaries_by_user(uuid.uuid4())

        assert result == []

    async def test_list_summaries_returns_dict_without_code(
        self, snippet_service, mock_db, sample_snippet
    ):
        """Test that summaries return dicts without code field."""
        summary = {
            "id": sample_snippet.id,
            "user_id": sample_snippet.user_id,
            "title": sample_snippet.title,
            "language": sample_snippet.language,
            "description": sample_snippet.description,
            "execution_count": sample_snippet.execution_count,
            "last_execution_at": sample_snippet.last_execution_at,
            "created_at": sample_snippet.created_at,
            "updated_at": sample_snippet.updated_at,
        }
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [summary]
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        result = await snippet_service.list_summaries_by_user(sample_snippet.user_id)

        assert len(result) == 1
        assert "code" not in result[0]
        assert result[0]["id"] == sample_snippet.id


class TestSnippetServiceUpdate:
    """Tests for SnippetService.update()."""

    async def test_update_code(self, snippet_service, mock_db, sample_snippet):
        """Test updating snippet code."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snippet
        mock_db.execute.return_value = mock_result

        new_code = "print('updated')"
        result = await snippet_service.update(
            snippet_id=sample_snippet.id,
            user_id=sample_snippet.user_id,
            code=new_code,
        )

        assert result.code == new_code
        mock_db.flush.assert_called_once()

    async def test_update_not_found(self, snippet_service, mock_db):
        """Test updating a snippet that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await snippet_service.update(
            snippet_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            code="new code",
        )

        assert result is None


class TestSnippetServiceDelete:
    """Tests for SnippetService.delete()."""

    async def test_delete_success(self, snippet_service, mock_db, sample_snippet):
        """Test deleting an existing snippet."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snippet
        mock_db.execute.return_value = mock_result

        result = await snippet_service.delete(
            snippet_id=sample_snippet.id,
            user_id=sample_snippet.user_id,
        )

        assert result is True
        mock_db.delete.assert_called_once_with(sample_snippet)

    async def test_delete_not_found(self, snippet_service, mock_db):
        """Test deleting a snippet that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await snippet_service.delete(
            snippet_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        assert result is False
        mock_db.delete.assert_not_called()


class TestSnippetServiceRecordExecution:
    """Tests for SnippetService.record_execution()."""

    async def test_record_execution(self, snippet_service, mock_db, sample_snippet):
        """Test recording an execution."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snippet
        mock_db.execute.return_value = mock_result

        initial_count = sample_snippet.execution_count

        result = await snippet_service.record_execution(
            snippet_id=sample_snippet.id,
            user_id=sample_snippet.user_id,
        )

        assert result.execution_count == initial_count + 1
        assert result.last_execution_at is not None

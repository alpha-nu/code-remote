"""Unit tests for snippets router."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth.dependencies import get_current_user
from api.auth.models import User as CognitoUser
from api.models import Snippet, User
from api.routers.snippets import get_db_user, router
from api.services.database import get_db

# Create a test app with just the snippets router
app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_cognito_user():
    """Create a mock Cognito user."""
    return CognitoUser(
        id="test-cognito-sub",  # Cognito sub is stored in .id
        email="test@example.com",
        username="testuser",
        groups=None,
    )


@pytest.fixture
def mock_db_user():
    """Create a mock database user."""
    user = User(
        id=uuid.uuid4(),
        cognito_sub="test-cognito-sub",
        email="test@example.com",
        username="testuser",
    )
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


@pytest.fixture
def mock_snippet(mock_db_user):
    """Create a mock snippet."""
    snippet = Snippet(
        id=uuid.uuid4(),
        user_id=mock_db_user.id,
        code="print('hello')",
        title="Test Snippet",
        language="python",
        description="A test snippet",
        execution_count=0,
        is_starred=False,
    )
    snippet.created_at = datetime.now(UTC)
    snippet.updated_at = datetime.now(UTC)
    snippet.last_execution_at = None
    return snippet


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def client(mock_cognito_user, mock_db_user, mock_db):
    """Create a test client with mocked dependencies."""
    # Override auth dependency
    app.dependency_overrides[get_current_user] = lambda: mock_cognito_user

    # Override database dependency
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    # Override get_db_user to return the mock user
    app.dependency_overrides[get_db_user] = lambda: mock_db_user

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


class TestCreateSnippet:
    """Tests for POST /snippets."""

    def test_create_snippet_success(self, client, mock_db_user, mock_db):
        """Test successful snippet creation."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            # Set up mock
            mock_service = MockService.return_value
            created_snippet = Snippet(
                id=uuid.uuid4(),
                user_id=mock_db_user.id,
                code="print('hello')",
                title="New Snippet",
                language="python",
                description="Test description",
                execution_count=0,
                is_starred=False,
            )
            created_snippet.created_at = datetime.now(UTC)
            created_snippet.updated_at = datetime.now(UTC)
            created_snippet.last_execution_at = None

            mock_service.create = AsyncMock(return_value=created_snippet)

            response = client.post(
                "/snippets",
                json={
                    "code": "print('hello')",
                    "title": "New Snippet",
                    "description": "Test description",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["code"] == "print('hello')"
            assert data["title"] == "New Snippet"

    def test_create_snippet_minimal(self, client, mock_db_user, mock_db):
        """Test creating snippet with only required fields."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            created_snippet = Snippet(
                id=uuid.uuid4(),
                user_id=mock_db_user.id,
                code="x = 1",
                title=None,
                language="python",
                description=None,
                execution_count=0,
                is_starred=False,
            )
            created_snippet.created_at = datetime.now(UTC)
            created_snippet.updated_at = datetime.now(UTC)
            created_snippet.last_execution_at = None

            mock_service.create = AsyncMock(return_value=created_snippet)

            response = client.post(
                "/snippets",
                json={"code": "x = 1"},
            )

            assert response.status_code == 201

    def test_create_snippet_empty_code(self, client):
        """Test that empty code is rejected."""
        response = client.post(
            "/snippets",
            json={"code": ""},
        )

        assert response.status_code == 422  # Validation error


class TestListSnippets:
    """Tests for GET /snippets."""

    def test_list_snippets_empty(self, client, mock_db_user, mock_db):
        """Test listing snippets when user has none."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.list_summaries_by_user = AsyncMock(return_value=[])

            # Mock count query
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_db.execute = AsyncMock(return_value=mock_result)

            response = client.get("/snippets")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["total"] == 0

    def test_list_snippets_with_data(self, client, mock_db_user, mock_db, mock_snippet):
        """Test listing snippets with existing data (returns summary without code)."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            # list_summaries_by_user returns dict mappings, not Snippet objects
            summary = {
                "id": mock_snippet.id,
                "user_id": mock_snippet.user_id,
                "title": mock_snippet.title,
                "language": mock_snippet.language,
                "description": mock_snippet.description,
                "execution_count": mock_snippet.execution_count,
                "is_starred": mock_snippet.is_starred,
                "last_execution_at": mock_snippet.last_execution_at,
                "created_at": mock_snippet.created_at,
                "updated_at": mock_snippet.updated_at,
            }
            mock_service.list_summaries_by_user = AsyncMock(return_value=[summary])

            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_db.execute = AsyncMock(return_value=mock_result)

            response = client.get("/snippets")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["total"] == 1
            # Verify code is NOT in the response
            assert "code" not in data["items"][0]

    def test_list_snippets_pagination(self, client, mock_db_user, mock_db):
        """Test listing snippets with pagination parameters."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.list_summaries_by_user = AsyncMock(return_value=[])

            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_db.execute = AsyncMock(return_value=mock_result)

            response = client.get("/snippets?limit=10&offset=5")

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 10
            assert data["offset"] == 5


class TestGetSnippet:
    """Tests for GET /snippets/{snippet_id}."""

    def test_get_snippet_success(self, client, mock_db_user, mock_db, mock_snippet):
        """Test getting an existing snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_by_id = AsyncMock(return_value=mock_snippet)

            response = client.get(f"/snippets/{mock_snippet.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(mock_snippet.id)

    def test_get_snippet_not_found(self, client, mock_db_user, mock_db):
        """Test getting a non-existent snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_by_id = AsyncMock(return_value=None)

            response = client.get(f"/snippets/{uuid.uuid4()}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestUpdateSnippet:
    """Tests for PUT /snippets/{snippet_id}."""

    def test_update_snippet_success(self, client, mock_db_user, mock_db, mock_snippet):
        """Test updating a snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_snippet.code = "print('updated')"
            mock_service.update = AsyncMock(return_value=mock_snippet)

            response = client.put(
                f"/snippets/{mock_snippet.id}",
                json={"code": "print('updated')"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "print('updated')"

    def test_update_snippet_not_found(self, client, mock_db_user, mock_db):
        """Test updating a non-existent snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.update = AsyncMock(return_value=None)

            response = client.put(
                f"/snippets/{uuid.uuid4()}",
                json={"code": "new code"},
            )

            assert response.status_code == 404


class TestDeleteSnippet:
    """Tests for DELETE /snippets/{snippet_id}."""

    def test_delete_snippet_success(self, client, mock_db_user, mock_db, mock_snippet):
        """Test deleting a snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.delete = AsyncMock(return_value=True)

            response = client.delete(f"/snippets/{mock_snippet.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] is True

    def test_delete_snippet_not_found(self, client, mock_db_user, mock_db):
        """Test deleting a non-existent snippet."""
        with patch("api.routers.snippets.SnippetService") as MockService:
            mock_service = MockService.return_value
            mock_service.delete = AsyncMock(return_value=False)

            response = client.delete(f"/snippets/{uuid.uuid4()}")

            assert response.status_code == 404

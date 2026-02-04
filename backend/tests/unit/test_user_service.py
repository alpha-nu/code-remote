"""Unit tests for user service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.models import User
from api.services.user_service import UserService


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def user_service(mock_db):
    """Create a UserService with mock database."""
    return UserService(mock_db)


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    user = User(
        id=uuid.uuid4(),
        cognito_sub="cognito-sub-12345",
        email="test@example.com",
        username="testuser",
    )
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


class TestUserServiceGetOrCreateFromCognito:
    """Tests for UserService.get_or_create_from_cognito()."""

    async def test_creates_new_user(self, user_service, mock_db):
        """Test creating a new user from Cognito claims."""
        cognito_sub = "new-cognito-sub"
        email = "newuser@example.com"

        # Mock: user doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock refresh to set timestamps
        async def mock_refresh(user):
            user.id = uuid.uuid4()
            user.created_at = datetime.now(UTC)
            user.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await user_service.get_or_create_from_cognito(
            cognito_sub=cognito_sub,
            email=email,
        )

        mock_db.add.assert_called_once()
        assert result.cognito_sub == cognito_sub
        assert result.email == email
        assert result.last_login is not None

    async def test_returns_existing_user(self, user_service, mock_db, sample_user):
        """Test returning existing user from Cognito claims."""
        # Mock: user exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        result = await user_service.get_or_create_from_cognito(
            cognito_sub=sample_user.cognito_sub,
            email=sample_user.email,
        )

        mock_db.add.assert_not_called()
        assert result.id == sample_user.id
        assert result.last_login is not None

    async def test_updates_email_if_changed(self, user_service, mock_db, sample_user):
        """Test updating email when Cognito email changes."""
        new_email = "newemail@example.com"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        result = await user_service.get_or_create_from_cognito(
            cognito_sub=sample_user.cognito_sub,
            email=new_email,
        )

        assert result.email == new_email

    async def test_creates_username_from_email(self, user_service, mock_db):
        """Test auto-generating username from email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def mock_refresh(user):
            user.id = uuid.uuid4()
            user.created_at = datetime.now(UTC)
            user.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await user_service.get_or_create_from_cognito(
            cognito_sub="sub-123",
            email="john.doe@example.com",
        )

        # Username should be generated from email prefix
        assert result.username == "john.doe"


class TestUserServiceGetByCognitoSub:
    """Tests for UserService.get_by_cognito_sub()."""

    async def test_get_existing_user(self, user_service, mock_db, sample_user):
        """Test getting user by Cognito sub."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_cognito_sub(sample_user.cognito_sub)

        assert result == sample_user

    async def test_get_nonexistent_user(self, user_service, mock_db):
        """Test getting non-existent user by Cognito sub."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_cognito_sub("nonexistent-sub")

        assert result is None


class TestUserServiceGetById:
    """Tests for UserService.get_by_id()."""

    async def test_get_by_id(self, user_service, mock_db, sample_user):
        """Test getting user by internal UUID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_id(sample_user.id)

        assert result == sample_user

    async def test_get_by_id_not_found(self, user_service, mock_db):
        """Test getting non-existent user by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_id(uuid.uuid4())

        assert result is None


class TestUserServiceGetByEmail:
    """Tests for UserService.get_by_email()."""

    async def test_get_by_email(self, user_service, mock_db, sample_user):
        """Test getting user by email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_email(sample_user.email)

        assert result == sample_user

    async def test_get_by_email_not_found(self, user_service, mock_db):
        """Test getting non-existent user by email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await user_service.get_by_email("nonexistent@example.com")

        assert result is None

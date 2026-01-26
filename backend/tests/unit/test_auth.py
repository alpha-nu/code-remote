"""Unit tests for authentication module."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from api.auth.cognito import (
    CognitoAuth,
    InvalidTokenError,
    TokenExpiredError,
)
from api.auth.models import User


class TestUser:
    """Tests for User model."""

    def test_from_token_payload_basic(self):
        """Test creating user from basic token payload."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "cognito:username": "testuser",
        }

        user = User.from_token_payload(payload)

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.groups is None

    def test_from_token_payload_with_groups(self):
        """Test creating user with groups claim."""
        payload = {
            "sub": "user-456",
            "email": "admin@example.com",
            "cognito:username": "admin",
            "cognito:groups": ["admin", "users"],
        }

        user = User.from_token_payload(payload)

        assert user.id == "user-456"
        assert user.groups == ["admin", "users"]

    def test_from_token_payload_fallback_username(self):
        """Test username fallback when cognito:username is not present."""
        payload = {
            "sub": "user-789",
            "username": "fallback_user",
        }

        user = User.from_token_payload(payload)

        assert user.username == "fallback_user"

    def test_from_token_payload_minimal(self):
        """Test creating user with minimal claims."""
        payload = {"sub": "minimal-user"}

        user = User.from_token_payload(payload)

        assert user.id == "minimal-user"
        assert user.email is None
        assert user.username is None
        assert user.groups is None


class TestCognitoAuth:
    """Tests for CognitoAuth class."""

    def test_init_sets_urls(self):
        """Test that init correctly sets JWKS URL and issuer."""
        auth = CognitoAuth(
            user_pool_id="us-east-1_ABCD1234",
            client_id="test-client",
            region="us-east-1",
        )

        assert auth.jwks_url == (
            "https://cognito-idp.us-east-1.amazonaws.com/"
            "us-east-1_ABCD1234/.well-known/jwks.json"
        )
        assert auth.issuer == ("https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ABCD1234")

    @patch("api.auth.cognito.PyJWKClient")
    def test_decode_token_success(self, mock_jwk_client_class):
        """Test successful token decoding."""
        # Setup mocks
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwk_client_class.return_value = mock_jwk_client

        auth = CognitoAuth(
            user_pool_id="us-east-1_Test",
            client_id="test-client",
            region="us-east-1",
        )

        # Create a valid token for testing
        expected_payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "aud": "test-client",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Test",
            "exp": int(time.time()) + 3600,
        }

        with patch("api.auth.cognito.jwt.decode") as mock_decode:
            mock_decode.return_value = expected_payload

            result = auth.decode_token("fake-token")

            assert result == expected_payload
            mock_decode.assert_called_once()

    @patch("api.auth.cognito.PyJWKClient")
    def test_decode_token_expired(self, mock_jwk_client_class):
        """Test that expired token raises TokenExpiredError."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwk_client_class.return_value = mock_jwk_client

        auth = CognitoAuth(
            user_pool_id="us-east-1_Test",
            client_id="test-client",
            region="us-east-1",
        )

        with patch("api.auth.cognito.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

            with pytest.raises(TokenExpiredError) as exc_info:
                auth.decode_token("expired-token")

            assert "expired" in str(exc_info.value).lower()

    @patch("api.auth.cognito.PyJWKClient")
    def test_decode_token_invalid_audience(self, mock_jwk_client_class):
        """Test that invalid audience raises InvalidTokenError."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwk_client_class.return_value = mock_jwk_client

        auth = CognitoAuth(
            user_pool_id="us-east-1_Test",
            client_id="test-client",
            region="us-east-1",
        )

        with patch("api.auth.cognito.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidAudienceError("Invalid audience")

            with pytest.raises(InvalidTokenError) as exc_info:
                auth.decode_token("bad-audience-token")

            assert "audience" in str(exc_info.value).lower()

    @patch("api.auth.cognito.PyJWKClient")
    def test_is_token_valid_returns_true_for_valid(self, mock_jwk_client_class):
        """Test is_token_valid returns True for valid token."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwk_client_class.return_value = mock_jwk_client

        auth = CognitoAuth(
            user_pool_id="us-east-1_Test",
            client_id="test-client",
            region="us-east-1",
        )

        with patch("api.auth.cognito.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user-123"}

            assert auth.is_token_valid("valid-token") is True

    @patch("api.auth.cognito.PyJWKClient")
    def test_is_token_valid_returns_false_for_invalid(self, mock_jwk_client_class):
        """Test is_token_valid returns False for invalid token."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwk_client_class.return_value = mock_jwk_client

        auth = CognitoAuth(
            user_pool_id="us-east-1_Test",
            client_id="test-client",
            region="us-east-1",
        )

        with patch("api.auth.cognito.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.PyJWTError("Invalid")

            assert auth.is_token_valid("invalid-token") is False


class TestAuthDependencies:
    """Tests for authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_user_missing_token(self):
        """Test that missing token raises 401."""
        from api.auth.dependencies import get_current_user

        mock_auth = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None, auth=mock_auth)

        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test that expired token raises 401."""
        from fastapi.security import HTTPAuthorizationCredentials

        from api.auth.dependencies import get_current_user

        mock_auth = MagicMock()
        mock_auth.decode_token.side_effect = TokenExpiredError("Token expired")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired-token")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, auth=mock_auth)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test that invalid token raises 401."""
        from fastapi.security import HTTPAuthorizationCredentials

        from api.auth.dependencies import get_current_user

        mock_auth = MagicMock()
        mock_auth.decode_token.side_effect = InvalidTokenError("Invalid token")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, auth=mock_auth)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test that valid token returns User."""
        from fastapi.security import HTTPAuthorizationCredentials

        from api.auth.dependencies import get_current_user

        mock_auth = MagicMock()
        mock_auth.decode_token.return_value = {
            "sub": "user-123",
            "email": "test@example.com",
            "cognito:username": "testuser",
        }

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

        user = await get_current_user(credentials=credentials, auth=mock_auth)

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_none_when_no_token(self):
        """Test that optional user returns None when no token."""
        from api.auth.dependencies import get_optional_user

        mock_auth = MagicMock()

        user = await get_optional_user(credentials=None, auth=mock_auth)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_none_on_invalid_token(self):
        """Test that optional user returns None on invalid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        from api.auth.dependencies import get_optional_user

        mock_auth = MagicMock()
        mock_auth.decode_token.side_effect = InvalidTokenError("Invalid")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")

        user = await get_optional_user(credentials=credentials, auth=mock_auth)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_user_on_valid_token(self):
        """Test that optional user returns User on valid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        from api.auth.dependencies import get_optional_user

        mock_auth = MagicMock()
        mock_auth.decode_token.return_value = {
            "sub": "user-456",
            "email": "optional@example.com",
        }

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

        user = await get_optional_user(credentials=credentials, auth=mock_auth)

        assert user is not None
        assert user.id == "user-456"
        assert user.email == "optional@example.com"

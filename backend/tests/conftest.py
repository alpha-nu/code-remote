"""Pytest configuration and fixtures.

This module sets up test environment variables BEFORE any application
modules are imported, ensuring Settings validation passes in CI.
"""

import os

# Set test environment variables before any imports that might trigger Settings
# This runs at pytest collection time, before test modules are imported
os.environ.setdefault("APP_NAME", "code-remote-test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("EXECUTION_TIMEOUT_SECONDS", "30")
os.environ.setdefault("MAX_CODE_SIZE_BYTES", "10240")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/testdb")
os.environ.setdefault("GEMINI_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_TestPool")
os.environ.setdefault("COGNITO_CLIENT_ID", "test-client-id")
os.environ.setdefault("COGNITO_REGION", "us-east-1")
os.environ.setdefault("DEV_AUTH_BYPASS", "false")  # Ensure auth is required in tests

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Import here to ensure env vars are set first
    from api.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client():
    """Create a test client with mocked authentication.

    This fixture overrides the auth dependency to return a test user,
    allowing tests to bypass real JWT validation.
    """
    from api.auth.dependencies import get_current_user
    from api.auth.models import User
    from api.main import app

    test_user = User(
        id="test-user-123",
        email="test@example.com",
        username="testuser",
        groups=None,
    )

    # Override the dependency to return test user
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as test_client:
        yield test_client

    # Clean up override
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_env_vars():
    """Fixture providing standard test environment variables."""
    return {
        "APP_NAME": "code-remote-test",
        "DEBUG": "false",
        "ENVIRONMENT": "testing",
        "HOST": "127.0.0.1",
        "PORT": "8000",
        "CORS_ORIGINS": '["http://localhost:3000"]',
        "EXECUTION_TIMEOUT_SECONDS": "30",
        "MAX_CODE_SIZE_BYTES": "10240",
        "REDIS_URL": "redis://localhost:6379",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/testdb",
        "GEMINI_API_KEY": "test-api-key",
        "COGNITO_USER_POOL_ID": "us-east-1_TestPool",
        "COGNITO_CLIENT_ID": "test-client-id",
        "COGNITO_REGION": "us-east-1",
    }

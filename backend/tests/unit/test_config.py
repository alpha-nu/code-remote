"""Unit tests for configuration."""

import os
from unittest.mock import patch

from common.config import Settings, get_settings


def test_settings_loads_from_env_vars():
    """Test that settings load correctly from environment variables."""
    env_vars = {
        "APP_NAME": "test-app",
        "DEBUG": "true",
        "ENVIRONMENT": "testing",
        "HOST": "127.0.0.1",
        "PORT": "9000",
        "CORS_ORIGINS": '["http://example.com"]',
        "EXECUTION_TIMEOUT_SECONDS": "60",
        "MAX_CODE_SIZE_BYTES": "20480",
        "REDIS_URL": "redis://test:6379",
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "GEMINI_API_KEY": "test-key",
        "COGNITO_USER_POOL_ID": "us-east-1_TestPool",
        "COGNITO_CLIENT_ID": "test-client-id",
        "COGNITO_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings(_env_file=None)
        assert settings.app_name == "test-app"
        assert settings.debug is True
        assert settings.environment == "testing"
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.cors_origins == ["http://example.com"]
        assert settings.execution_timeout_seconds == 60
        assert settings.max_code_size_bytes == 20480
        assert settings.redis_url == "redis://test:6379"
        assert settings.database_url == "postgresql://test:test@localhost/testdb"
        assert settings.gemini_api_key == "test-key"


def test_settings_has_sensible_defaults():
    """Test that settings work with defaults when env vars are empty."""
    with patch.dict(os.environ, {}, clear=True):
        # Settings should work with defaults (no ValidationError)
        settings = Settings(_env_file=None)
        assert settings.app_name == "Code Remote"
        assert settings.environment == "development"
        assert settings.execution_timeout_seconds == 30


def test_settings_cors_origins_parses_json():
    """Test that CORS origins parses JSON array."""
    env_vars = {
        "APP_NAME": "test",
        "DEBUG": "false",
        "ENVIRONMENT": "test",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "CORS_ORIGINS": '["http://localhost:3000", "http://localhost:5173"]',
        "EXECUTION_TIMEOUT_SECONDS": "30",
        "MAX_CODE_SIZE_BYTES": "10240",
        "REDIS_URL": "redis://localhost:6379",
        "DATABASE_URL": "postgresql://localhost/db",
        "GEMINI_API_KEY": "",
        "COGNITO_USER_POOL_ID": "us-east-1_Test",
        "COGNITO_CLIENT_ID": "test-client",
        "COGNITO_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings(_env_file=None)
        assert len(settings.cors_origins) == 2
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://localhost:5173" in settings.cors_origins


def test_get_settings_returns_cached_instance():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2

"""Unit tests for configuration."""

import os
from unittest.mock import patch

from common.config import Settings, get_settings


def test_settings_default_values():
    """Test that settings have correct default values when no env vars set."""
    # Create settings without loading .env file
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.app_name == "code-remote"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.port == 8000
        assert settings.execution_timeout_seconds == 30
        assert settings.max_code_size_bytes == 10240


def test_settings_cors_origins_default():
    """Test that CORS origins have localhost defaults."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://localhost:5173" in settings.cors_origins


def test_get_settings_returns_cached_instance():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2

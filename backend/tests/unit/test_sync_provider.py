"""Unit tests for the sync provider factory and dynamic class loading."""

from unittest.mock import MagicMock, patch

import pytest

from api.services.sync.provider import SyncProvider, _load_provider_class


class TestLoadProviderClass:
    """Tests for _load_provider_class dynamic import."""

    def test_loads_sqs_provider(self):
        """Test loading the SQS sync provider class."""
        cls = _load_provider_class("api.services.sync.sqs.SQSSyncProvider")
        from api.services.sync.sqs import SQSSyncProvider

        assert cls is SQSSyncProvider

    def test_loads_direct_provider(self):
        """Test loading the direct sync provider class."""
        cls = _load_provider_class("api.services.sync.direct.DirectSyncProvider")
        from api.services.sync.direct import DirectSyncProvider

        assert cls is DirectSyncProvider

    def test_loaded_class_is_sync_provider_subclass(self):
        """Test that loaded classes are SyncProvider subclasses."""
        cls = _load_provider_class("api.services.sync.direct.DirectSyncProvider")
        assert issubclass(cls, SyncProvider)

    def test_rejects_simple_name_without_dots(self):
        """Test that a bare name without module path is rejected."""
        with pytest.raises(ValueError, match="fully-qualified class name"):
            _load_provider_class("DirectSyncProvider")

    def test_rejects_nonexistent_module(self):
        """Test that a nonexistent module raises ValueError."""
        with pytest.raises(ValueError, match="Cannot import module"):
            _load_provider_class("api.services.sync.nonexistent.FakeProvider")

    def test_rejects_nonexistent_class_in_valid_module(self):
        """Test that a missing class in an existing module raises ValueError."""
        with pytest.raises(ValueError, match="has no attribute"):
            _load_provider_class("api.services.sync.direct.NonexistentProvider")

    def test_rejects_non_sync_provider_class(self):
        """Test that a class that isn't a SyncProvider subclass is rejected."""
        # logging.Logger exists but is not a SyncProvider
        with pytest.raises(ValueError, match="not a SyncProvider subclass"):
            _load_provider_class("logging.Logger")

    def test_rejects_non_class_attribute(self):
        """Test that a non-class attribute (e.g. a function) is rejected."""
        with pytest.raises(ValueError, match="not a SyncProvider subclass"):
            _load_provider_class("os.path.join")


class TestGetSyncProvider:
    """Tests for get_sync_provider factory."""

    def test_returns_none_when_not_configured(self):
        """Test that empty SYNC_PROVIDER returns None."""
        from api.services.sync.provider import get_sync_provider

        # Clear lru_cache before each test
        get_sync_provider.cache_clear()

        with patch("api.services.sync.provider.settings") as mock_settings:
            mock_settings.sync_provider = ""
            result = get_sync_provider()

        assert result is None

    def test_returns_direct_provider_instance(self):
        """Test that DirectSyncProvider class path returns an instance."""
        from api.services.sync.direct import DirectSyncProvider
        from api.services.sync.provider import get_sync_provider

        get_sync_provider.cache_clear()

        with patch("api.services.sync.provider.settings") as mock_settings:
            mock_settings.sync_provider = "api.services.sync.direct.DirectSyncProvider"
            result = get_sync_provider()

        assert isinstance(result, DirectSyncProvider)

    def test_returns_sqs_provider_instance(self):
        """Test that SQSSyncProvider class path returns an instance."""
        from api.services.sync.provider import get_sync_provider
        from api.services.sync.sqs import SQSSyncProvider

        get_sync_provider.cache_clear()

        with (
            patch("api.services.sync.provider.settings") as mock_factory_settings,
            patch("api.services.sync.sqs.settings") as mock_sqs_settings,
            patch("api.services.sync.sqs._get_sqs_client") as mock_client,
        ):
            mock_factory_settings.sync_provider = "api.services.sync.sqs.SQSSyncProvider"
            mock_sqs_settings.snippet_sync_queue_url = "https://sqs.test/queue.fifo"
            mock_client.return_value = MagicMock()

            result = get_sync_provider()

        assert isinstance(result, SQSSyncProvider)

    def test_raises_for_invalid_class_path(self):
        """Test that an invalid class path raises ValueError."""
        from api.services.sync.provider import get_sync_provider

        get_sync_provider.cache_clear()

        with patch("api.services.sync.provider.settings") as mock_settings:
            mock_settings.sync_provider = "nonexistent.module.FakeProvider"
            with pytest.raises(ValueError, match="Cannot import module"):
                get_sync_provider()

    def test_result_is_cached(self):
        """Test that the factory caches the provider instance."""
        from api.services.sync.provider import get_sync_provider

        get_sync_provider.cache_clear()

        with patch("api.services.sync.provider.settings") as mock_settings:
            mock_settings.sync_provider = "api.services.sync.direct.DirectSyncProvider"
            result1 = get_sync_provider()
            result2 = get_sync_provider()

        assert result1 is result2


class TestSQSSyncProviderInit:
    """Tests for SQSSyncProvider construction."""

    def test_init_with_explicit_queue_url(self):
        """Test construction with explicit queue_url argument."""
        from api.services.sync.sqs import SQSSyncProvider

        mock_client = MagicMock()
        provider = SQSSyncProvider(
            queue_url="https://sqs.test/queue.fifo",
            sqs_client=mock_client,
        )
        assert provider._queue_url == "https://sqs.test/queue.fifo"
        assert provider._sqs is mock_client

    def test_init_falls_back_to_settings(self):
        """Test construction reads queue_url from settings when not provided."""
        from api.services.sync.sqs import SQSSyncProvider

        with (
            patch("api.services.sync.sqs.settings") as mock_settings,
            patch("api.services.sync.sqs._get_sqs_client") as mock_client_factory,
        ):
            mock_settings.snippet_sync_queue_url = "https://sqs.settings/queue.fifo"
            mock_client_factory.return_value = MagicMock()

            provider = SQSSyncProvider()

        assert provider._queue_url == "https://sqs.settings/queue.fifo"

    def test_init_raises_when_no_queue_url(self):
        """Test construction raises RuntimeError when no queue URL is available."""
        from api.services.sync.sqs import SQSSyncProvider

        with patch("api.services.sync.sqs.settings") as mock_settings:
            mock_settings.snippet_sync_queue_url = ""
            with pytest.raises(RuntimeError, match="SNIPPET_SYNC_QUEUE_URL"):
                SQSSyncProvider()

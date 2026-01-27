"""Unit tests for the complexity analyzer."""

from unittest.mock import patch

import pytest

from analyzer.complexity import ComplexityAnalyzer
from analyzer.llm_provider import ComplexityResult


class MockProvider:
    """Mock LLM provider for testing."""

    def __init__(self, result: ComplexityResult | None = None, configured: bool = True):
        self.result = result or ComplexityResult(
            time_complexity="O(n)",
            space_complexity="O(1)",
            time_explanation="Linear iteration",
            space_explanation="Constant space",
        )
        self._configured = configured

    async def analyze_complexity(self, code: str) -> ComplexityResult:
        return self.result

    def is_configured(self) -> bool:
        return self._configured


class TestComplexityAnalyzer:
    """Tests for ComplexityAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyze_returns_complexity_result(self):
        """Test that analyze returns a ComplexityResult."""
        provider = MockProvider()
        analyzer = ComplexityAnalyzer(provider=provider)

        result = await analyzer.analyze("for i in range(n): print(i)")

        assert result.time_complexity == "O(n)"
        assert result.space_complexity == "O(1)"
        assert result.time_explanation == "Linear iteration"

    @pytest.mark.asyncio
    async def test_analyze_empty_code_returns_error(self):
        """Test that empty code returns an error result."""
        provider = MockProvider()
        analyzer = ComplexityAnalyzer(provider=provider)

        result = await analyzer.analyze("")

        assert result.time_complexity == "N/A"
        assert result.error == "Empty code"

    @pytest.mark.asyncio
    async def test_analyze_whitespace_only_returns_error(self):
        """Test that whitespace-only code returns an error."""
        provider = MockProvider()
        analyzer = ComplexityAnalyzer(provider=provider)

        result = await analyzer.analyze("   \n\t  ")

        assert result.error == "Empty code"

    def test_is_available_returns_provider_status(self):
        """Test that is_available reflects provider configuration."""
        configured_provider = MockProvider(configured=True)
        unconfigured_provider = MockProvider(configured=False)

        assert ComplexityAnalyzer(provider=configured_provider).is_available() is True
        assert ComplexityAnalyzer(provider=unconfigured_provider).is_available() is False


class TestComplexityResult:
    """Tests for ComplexityResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = ComplexityResult(
            time_complexity="O(1)",
            space_complexity="O(1)",
            time_explanation="Constant",
            space_explanation="Constant",
        )

        assert result.algorithm_identified is None
        assert result.suggestions is None
        assert result.raw_response is None
        assert result.error is None

    def test_all_fields(self):
        """Test all fields can be set."""
        result = ComplexityResult(
            time_complexity="O(n log n)",
            space_complexity="O(n)",
            time_explanation="Merge sort",
            space_explanation="Auxiliary array",
            algorithm_identified="Merge Sort",
            suggestions=["Consider in-place sort"],
            raw_response='{"time": "O(n log n)"}',
            error=None,
        )

        assert result.time_complexity == "O(n log n)"
        assert result.algorithm_identified == "Merge Sort"
        assert len(result.suggestions) == 1


class TestGeminiProviderIntegration:
    """Integration tests for Gemini provider (mocked)."""

    @pytest.mark.asyncio
    async def test_gemini_provider_not_configured(self):
        """Test that unconfigured provider returns appropriate error."""
        with patch("analyzer.providers.gemini.settings") as mock_settings:
            mock_settings.gemini_api_key = ""

            # Import after patching
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="")

            result = await provider.analyze_complexity("print('hello')")

            assert result.error == "GEMINI_API_KEY not set"
            assert result.time_complexity == "Unknown"

    def test_gemini_provider_is_configured(self):
        """Test is_configured with API key."""
        with (
            patch("google.genai.Client"),
            patch("analyzer.providers.gemini.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = ""

            from analyzer.providers.gemini import GeminiProvider

            # Create fresh instances with explicit API keys
            provider_with_key = GeminiProvider(api_key="test-key")
            provider_without_key = GeminiProvider(api_key="")

            # Check directly based on the api_key passed
            assert provider_with_key.api_key == "test-key"
            assert provider_with_key.is_configured() is True
            assert provider_without_key.api_key == ""
            assert provider_without_key.is_configured() is False

    def test_parse_response_strips_markdown(self):
        """Test that markdown code blocks are stripped from response."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            json_response = '```json\n{"time_complexity": "O(1)", "space_complexity": "O(1)", "time_explanation": "test", "space_explanation": "test"}\n```'
            result = provider._parse_response(json_response)

            assert result.time_complexity == "O(1)"

    def test_parse_response_handles_plain_json(self):
        """Test that plain JSON is parsed correctly."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            json_response = '{"time_complexity": "O(n^2)", "space_complexity": "O(1)", "time_explanation": "nested loops", "space_explanation": "no extra space"}'
            result = provider._parse_response(json_response)

            assert result.time_complexity == "O(n^2)"
            assert result.space_explanation == "no extra space"

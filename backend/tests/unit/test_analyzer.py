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
            narrative="### Algorithm\nLinear scan.\n\n### Time Complexity: O(n)\nSingle pass.\n\n### Space Complexity: O(1)\nConstant space.",
        )
        self._configured = configured

    async def analyze_complexity(self, code: str) -> ComplexityResult:
        return self.result

    async def analyze_complexity_stream(self, code: str):
        # Yield narrative in chunks, then final result
        narrative = self.result.narrative
        mid = len(narrative) // 2
        yield narrative[:mid]
        yield narrative[mid:]
        yield self.result

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
        assert "Linear scan" in result.narrative

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

    @pytest.mark.asyncio
    async def test_analyze_stream_yields_chunks_then_result(self):
        """Test that analyze_stream yields str chunks then ComplexityResult."""
        provider = MockProvider()
        analyzer = ComplexityAnalyzer(provider=provider)

        chunks = []
        final_result = None
        async for item in analyzer.analyze_stream("for i in range(n): print(i)"):
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, ComplexityResult):
                final_result = item

        assert len(chunks) == 2
        assert "".join(chunks) == provider.result.narrative
        assert final_result is not None
        assert final_result.time_complexity == "O(n)"

    @pytest.mark.asyncio
    async def test_analyze_stream_empty_code(self):
        """Test that analyze_stream yields error result for empty code."""
        provider = MockProvider()
        analyzer = ComplexityAnalyzer(provider=provider)

        items = []
        async for item in analyzer.analyze_stream(""):
            items.append(item)

        assert len(items) == 1
        assert isinstance(items[0], ComplexityResult)
        assert items[0].error == "Empty code"

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
            narrative="Constant time and space.",
        )

        assert result.raw_response is None
        assert result.error is None
        assert result.model is None

    def test_all_fields(self):
        """Test all fields can be set."""
        result = ComplexityResult(
            time_complexity="O(n log n)",
            space_complexity="O(n)",
            narrative="### Algorithm\nMerge Sort.",
            raw_response="raw text here",
            error=None,
            model="gemini-2.0-flash",
        )

        assert result.time_complexity == "O(n log n)"
        assert "Merge Sort" in result.narrative


class TestGeminiProviderIntegration:
    """Integration tests for Gemini provider (mocked)."""

    @pytest.mark.asyncio
    async def test_gemini_provider_not_configured(self):
        """Test that unconfigured provider returns appropriate error."""
        with patch("analyzer.providers.gemini.settings") as mock_settings:
            mock_settings.resolved_gemini_api_key = ""

            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="")

            result = await provider.analyze_complexity("print('hello')")

            assert result.time_complexity == "Unknown"
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_gemini_provider_stream_not_configured(self):
        """Test that unconfigured provider stream yields error result."""
        with patch("analyzer.providers.gemini.settings") as mock_settings:
            mock_settings.resolved_gemini_api_key = ""

            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="")

            items = []
            async for item in provider.analyze_complexity_stream("print('hello')"):
                items.append(item)

            assert len(items) == 1
            assert isinstance(items[0], ComplexityResult)
            assert items[0].error is not None

    def test_gemini_provider_is_configured(self):
        """Test is_configured with API key."""
        with (
            patch("google.genai.Client"),
            patch("analyzer.providers.gemini.settings") as mock_settings,
        ):
            mock_settings.resolved_gemini_api_key = ""

            from analyzer.providers.gemini import GeminiProvider

            provider_with_key = GeminiProvider(api_key="test-key")
            provider_without_key = GeminiProvider(api_key="")

            assert provider_with_key.is_configured() is True
            assert provider_without_key.is_configured() is False

    def test_parse_response_narrative_with_json_block(self):
        """Test that narrative + JSON block is parsed correctly."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = (
                "### Algorithm\nBubble sort.\n\n"
                "### Time Complexity: O(n²)\nNested loops.\n\n"
                "### Space Complexity: O(1)\nIn-place.\n\n"
                '```json\n{"time_complexity": "O(n²)", "space_complexity": "O(1)"}\n```'
            )
            result = provider._parse_response(raw)

            assert result.time_complexity == "O(n²)"
            assert result.space_complexity == "O(1)"
            assert "Bubble sort" in result.narrative
            assert "```json" not in result.narrative

    def test_parse_response_json_block_no_trailing_newline(self):
        """Test JSON block without newline before closing backticks."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = (
                "### Algorithm\nLinear scan.\n\n"
                '```json\n{"time_complexity": "O(n)", "space_complexity": "O(1)"}```'
            )
            result = provider._parse_response(raw)

            assert result.time_complexity == "O(n)"
            assert result.space_complexity == "O(1)"
            assert result.error is None

    def test_parse_response_json_block_uppercase_label(self):
        """Test JSON block with uppercase ```JSON label."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = (
                "### Algorithm\nMerge sort.\n\n"
                '```JSON\n{"time_complexity": "O(n log n)", "space_complexity": "O(n)"}\n```'
            )
            result = provider._parse_response(raw)

            assert result.time_complexity == "O(n log n)"
            assert result.space_complexity == "O(n)"
            assert result.error is None

    def test_parse_response_json_block_compact(self):
        """Test JSON block with no newlines inside fences."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = (
                "### Algorithm\nHash lookup.\n\n"
                '```json{"time_complexity": "O(1)", "space_complexity": "O(n)"}```'
            )
            result = provider._parse_response(raw)

            assert result.time_complexity == "O(1)"
            assert result.space_complexity == "O(n)"
            assert result.error is None

    def test_parse_response_heading_fallback(self):
        """Test extraction from headings when JSON block is absent."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = (
                "### Algorithm\nBinary search.\n\n"
                "### Time Complexity: O(log n)\nHalves the search space.\n\n"
                "### Space Complexity: O(1)\nIterative approach."
            )
            result = provider._parse_response(raw)

            assert result.time_complexity == "O(log n)"
            assert result.space_complexity == "O(1)"
            assert result.error is None
            assert "Binary search" in result.narrative

    def test_parse_response_no_json_block_no_headings(self):
        """Test response with neither JSON block nor complexity headings."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = "### Algorithm\nSomething without complexity info."
            result = provider._parse_response(raw)

            assert result.time_complexity == "Unknown"
            assert result.error is not None
            assert "Something without complexity info" in result.narrative

    def test_parse_response_invalid_json(self):
        """Test response with invalid JSON in the block."""
        with patch("google.genai.Client"):
            from analyzer.providers.gemini import GeminiProvider

            provider = GeminiProvider(api_key="test-key")

            raw = "### Algorithm\nTest.\n\n```json\n{invalid json}\n```"
            result = provider._parse_response(raw)

            assert result.time_complexity == "Unknown"
            assert "JSON parse error" in result.error

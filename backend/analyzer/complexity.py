"""Complexity analyzer service."""

from collections.abc import AsyncGenerator

from analyzer.llm_provider import ComplexityResult, LLMProvider
from analyzer.providers.gemini import get_gemini_provider


class ComplexityAnalyzer:
    """Service for analyzing code complexity using LLM."""

    def __init__(self, provider: LLMProvider | None = None):
        """Initialize the analyzer.

        Args:
            provider: LLM provider to use. Defaults to Gemini.
        """
        self.provider = provider or get_gemini_provider()

    def _empty_code_result(self) -> ComplexityResult:
        """Return an error result for empty/blank code."""
        return ComplexityResult(
            time_complexity="N/A",
            space_complexity="N/A",
            narrative="No code provided.",
            error="Empty code",
        )

    async def analyze(self, code: str) -> ComplexityResult:
        """Analyze the complexity of Python code (non-streaming).

        Used as the sync HTTP fallback.

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with time and space complexity analysis
        """
        if not code or not code.strip():
            return self._empty_code_result()

        return await self.provider.analyze_complexity(code)

    async def analyze_stream(self, code: str) -> AsyncGenerator[str | ComplexityResult, None]:
        """Stream complexity analysis chunks then a final result.

        Used for WebSocket streaming.

        Yields:
            str: Raw text chunks from the LLM.
            ComplexityResult: Final parsed result (last item).
        """
        if not code or not code.strip():
            yield self._empty_code_result()
            return

        async for item in self.provider.analyze_complexity_stream(code):
            yield item

    def is_available(self) -> bool:
        """Check if complexity analysis is available.

        Returns:
            True if LLM provider is configured
        """
        return self.provider.is_configured()


# Singleton instance
_analyzer: ComplexityAnalyzer | None = None


def get_complexity_analyzer() -> ComplexityAnalyzer:
    """Get or create the complexity analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ComplexityAnalyzer()
    return _analyzer

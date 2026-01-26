"""Complexity analyzer service."""

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

    async def analyze(self, code: str) -> ComplexityResult:
        """Analyze the complexity of Python code.

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with time and space complexity analysis
        """
        # Basic validation
        if not code or not code.strip():
            return ComplexityResult(
                time_complexity="N/A",
                space_complexity="N/A",
                time_explanation="No code provided",
                space_explanation="No code provided",
                error="Empty code",
            )

        return await self.provider.analyze_complexity(code)

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

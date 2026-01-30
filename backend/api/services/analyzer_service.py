"""Analyzer service for API layer."""

from analyzer import ComplexityResult, get_complexity_analyzer
from api.schemas.analysis import AnalyzeResponse


class AnalyzerService:
    """Service for complexity analysis."""

    def __init__(self):
        """Initialize the analyzer service."""
        self._analyzer = get_complexity_analyzer()

    async def analyze(self, code: str) -> AnalyzeResponse:
        """Analyze code complexity.

        Args:
            code: Python code to analyze

        Returns:
            AnalyzeResponse with complexity analysis
        """
        result: ComplexityResult = await self._analyzer.analyze(code)

        return AnalyzeResponse(
            success=result.error is None,
            time_complexity=result.time_complexity,
            space_complexity=result.space_complexity,
            time_explanation=result.time_explanation,
            space_explanation=result.space_explanation,
            algorithm_identified=result.algorithm_identified,
            suggestions=result.suggestions,
            error=result.error,
            available=self._analyzer.is_available(),
            model=result.model,
        )

    def is_available(self) -> bool:
        """Check if analysis is available."""
        return self._analyzer.is_available()


# Singleton instance
_service: AnalyzerService | None = None


def get_analyzer_service() -> AnalyzerService:
    """Get or create analyzer service singleton."""
    global _service
    if _service is None:
        _service = AnalyzerService()
    return _service

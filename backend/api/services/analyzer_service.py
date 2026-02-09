"""Analyzer service for API layer."""

from collections.abc import AsyncGenerator

from analyzer import ComplexityResult, get_complexity_analyzer
from api.schemas.analysis import AnalyzeResponse


class AnalyzerService:
    """Service for complexity analysis."""

    def __init__(self):
        """Initialize the analyzer service."""
        self._analyzer = get_complexity_analyzer()

    async def analyze(self, code: str) -> AnalyzeResponse:
        """Analyze code complexity (non-streaming, for sync HTTP fallback).

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
            narrative=result.narrative,
            error=result.error,
            available=self._analyzer.is_available(),
            model=result.model,
        )

    async def analyze_stream(self, code: str) -> AsyncGenerator[str | AnalyzeResponse, None]:
        """Stream analysis chunks, then yield the final AnalyzeResponse.

        Used for WebSocket streaming.

        Yields:
            str: Raw text chunks from the LLM.
            AnalyzeResponse: Final parsed result (last item).
        """
        async for item in self._analyzer.analyze_stream(code):
            if isinstance(item, str):
                yield item
            elif isinstance(item, ComplexityResult):
                yield AnalyzeResponse(
                    success=item.error is None,
                    time_complexity=item.time_complexity,
                    space_complexity=item.space_complexity,
                    narrative=item.narrative,
                    error=item.error,
                    available=self._analyzer.is_available(),
                    model=item.model,
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

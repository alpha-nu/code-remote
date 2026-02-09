"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class ComplexityResult:
    """Result of complexity analysis.

    The new prompt returns a Markdown narrative (streamed to the user)
    plus a trailing JSON block with structured complexity values.
    """

    time_complexity: str
    space_complexity: str
    narrative: str  # Full Markdown narrative (algorithm, explanations, suggestions)
    raw_response: str | None = None
    error: str | None = None
    model: str | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def analyze_complexity(self, code: str) -> ComplexityResult:
        """Analyze code complexity using the LLM (non-streaming).

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with analysis details
        """
        pass

    @abstractmethod
    def analyze_complexity_stream(self, code: str) -> AsyncGenerator[str | ComplexityResult, None]:
        """Analyze code complexity using the LLM with streaming.

        Yields str chunks of the Markdown narrative as they arrive,
        then yields a final ComplexityResult with the parsed structured data.

        Args:
            code: Python code to analyze

        Yields:
            str: Raw text chunks from the LLM
            ComplexityResult: Final parsed result (last item yielded)
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.

        Returns:
            True if API key and other requirements are met
        """
        pass

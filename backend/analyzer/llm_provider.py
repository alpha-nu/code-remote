"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ComplexityResult:
    """Result of complexity analysis."""

    time_complexity: str
    space_complexity: str
    time_explanation: str
    space_explanation: str
    algorithm_identified: str | None = None
    suggestions: list[str] | None = None
    raw_response: str | None = None
    error: str | None = None
    model: str | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def analyze_complexity(self, code: str) -> ComplexityResult:
        """Analyze code complexity using the LLM.

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with analysis details
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.

        Returns:
            True if API key and other requirements are met
        """
        pass

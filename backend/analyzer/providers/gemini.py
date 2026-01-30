"""Google Gemini LLM provider for code analysis."""

import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from analyzer.llm_provider import ComplexityResult, LLMProvider
from common.config import settings

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent / "prompts" / "complexity.txt"


class GeminiProvider(LLMProvider):
    """Gemini-based LLM provider for complexity analysis."""

    def __init__(self, api_key: str | None = None):
        """Initialize the Gemini provider.

        Args:
            api_key: Gemini API key. If not provided, uses settings lazily.
        """
        self._explicit_api_key = api_key
        self._client: genai.Client | None = None
        self._prompt_template: str | None = None
        self._model: str | None = None  # Loaded from settings during init
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the Gemini client."""
        if self._initialized:
            return

        self._initialized = True
        # Get API key (either explicit or from settings)
        self.api_key = self._explicit_api_key or settings.resolved_gemini_api_key
        # Get model from settings
        self._model = settings.gemini_model

        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini client initialized with model: {self._model}")
        else:
            logger.warning("Gemini API key not configured")

    def is_configured(self) -> bool:
        """Check if Gemini API key is configured."""
        self._ensure_initialized()
        return bool(self.api_key)

    def _load_prompt_template(self) -> str:
        """Load the complexity prompt template."""
        if self._prompt_template is None:
            if PROMPT_PATH.exists():
                self._prompt_template = PROMPT_PATH.read_text()
            else:
                # Fallback inline prompt
                self._prompt_template = """
Analyze this Python code's complexity:
```python
{code}
```

Respond with JSON only:
{{"time_complexity": "O(...)", "space_complexity": "O(...)", "time_explanation": "...", "space_explanation": "...", "algorithm_identified": "...", "suggestions": []}}
"""
        return self._prompt_template

    async def analyze_complexity(self, code: str) -> ComplexityResult:
        """Analyze code complexity using Gemini.

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with analysis
        """
        if not self.is_configured() or self._client is None:
            return ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                time_explanation="Gemini API key not configured",
                space_explanation="Gemini API key not configured",
                error="GEMINI_API_KEY not set",
                model=self._model,
            )

        try:
            prompt = self._load_prompt_template().format(code=code)

            # Generate response using the new SDK async API
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent analysis
                    max_output_tokens=2048,  # Increased for detailed responses
                ),
            )

            raw_text = response.text.strip() if response.text else ""

            # Log raw response for debugging
            logger.debug(f"Raw Gemini response: {repr(raw_text)}")

            # Parse JSON response
            return self._parse_response(raw_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            return ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                time_explanation="Failed to parse LLM response",
                space_explanation="Failed to parse LLM response",
                raw_response=raw_text if "raw_text" in locals() else None,
                error=f"JSON parse error: {str(e)}",
                model=self._model,
            )
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                time_explanation="LLM analysis failed",
                space_explanation="LLM analysis failed",
                error=str(e),
                model=self._model,
            )

    def _parse_response(self, raw_text: str) -> ComplexityResult:
        """Parse the JSON response from Gemini.

        Args:
            raw_text: Raw response text from Gemini

        Returns:
            Parsed ComplexityResult
        """
        # Strip markdown code blocks if present
        text = raw_text
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)

        return ComplexityResult(
            time_complexity=data.get("time_complexity", "Unknown"),
            space_complexity=data.get("space_complexity", "Unknown"),
            time_explanation=data.get("time_explanation", ""),
            space_explanation=data.get("space_explanation", ""),
            algorithm_identified=data.get("algorithm_identified"),
            suggestions=data.get("suggestions"),
            raw_response=raw_text,
            model=self._model,
        )


# Singleton instance
_provider: GeminiProvider | None = None


def get_gemini_provider() -> GeminiProvider:
    """Get or create the Gemini provider singleton."""
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider

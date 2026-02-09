"""Google Gemini LLM provider for code analysis."""

import json
import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from google import genai
from google.genai import types

from analyzer.llm_provider import ComplexityResult, LLMProvider
from common.config import settings
from common.tracing import add_llm_response_attributes, llm_span

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent / "prompts" / "complexity.txt"

# Pattern to find the trailing ```json {...} ``` block
# Case-insensitive, flexible whitespace (LLMs sometimes omit newlines).
_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

# Fallback: extract O(...) from Markdown headings when the JSON block is absent.
_TIME_HEADING_RE = re.compile(r"###\s*Time\s+Complexity\s*[:：]\s*(O\([^)]*\))", re.IGNORECASE)
_SPACE_HEADING_RE = re.compile(r"###\s*Space\s+Complexity\s*[:：]\s*(O\([^)]*\))", re.IGNORECASE)


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
        self._model: str | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the Gemini client."""
        if self._initialized:
            return

        self._initialized = True
        self.api_key = self._explicit_api_key or settings.resolved_gemini_api_key
        try:
            self._model = settings.resolved_llm_analysis_model
        except ValueError:
            self._model = None

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
                self._prompt_template = (
                    "Analyze this Python code's complexity:\n"
                    "```python\n{code}\n```\n\n"
                    "Respond with Markdown analysis then a JSON block:\n"
                    '```json\n{{"time_complexity": "O(...)", "space_complexity": "O(...)"}}\n```'
                )
        return self._prompt_template

    def _build_gen_config(self) -> tuple[str, types.GenerateContentConfig]:
        """Build generation config from settings.

        Returns:
            Tuple of (model_name, GenerateContentConfig).
        """
        model = settings.resolved_llm_analysis_model
        temperature = settings.resolved_llm_analysis_temperature
        max_output_tokens = settings.resolved_llm_analysis_max_tokens
        thinking_budget = settings.resolved_llm_analysis_thinking_budget

        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if thinking_budget is not None:
            gen_config.thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)
        return model, gen_config

    def _not_configured_result(self) -> ComplexityResult:
        """Return an error result when API key is not set."""
        return ComplexityResult(
            time_complexity="Unknown",
            space_complexity="Unknown",
            narrative="",
            error="GEMINI_API_KEY not set",
            model=self._model,
        )

    # ------------------------------------------------------------------
    # Non-streaming (sync HTTP fallback)
    # ------------------------------------------------------------------

    async def analyze_complexity(self, code: str) -> ComplexityResult:
        """Analyze code complexity using Gemini (non-streaming).

        Args:
            code: Python code to analyze

        Returns:
            ComplexityResult with narrative and structured complexity values.
        """
        if not self.is_configured() or self._client is None:
            return self._not_configured_result()

        try:
            prompt = self._load_prompt_template().format(code=code)
            model, gen_config = self._build_gen_config()

            logger.info(f"Gemini request: model={model}")

            with llm_span(
                "generate_content",
                model,
                operation_type="complexity_analysis",
                prompt_chars=len(prompt),
            ) as span:
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=gen_config,
                )

                raw_text = response.text.strip() if response.text else ""

                usage = response.usage_metadata
                add_llm_response_attributes(
                    span,
                    response_chars=len(raw_text),
                    response_truncated=raw_text[:200] if raw_text else None,
                    finish_reason=str(response.candidates[0].finish_reason)
                    if response.candidates
                    else None,
                    input_tokens=usage.prompt_token_count if usage else None,
                    output_tokens=usage.candidates_token_count if usage else None,
                    thinking_tokens=usage.thoughts_token_count if usage else None,
                    total_tokens=usage.total_token_count if usage else None,
                    response_id=response.response_id,
                    model_version=getattr(response, "model_version", None),
                )

            logger.debug(f"Raw Gemini response: {repr(raw_text[:300])}")
            return self._parse_response(raw_text, model=model)

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                narrative="",
                error=str(e),
                model=self._model,
            )

    # ------------------------------------------------------------------
    # Streaming (WebSocket push)
    # ------------------------------------------------------------------

    async def analyze_complexity_stream(
        self, code: str
    ) -> AsyncGenerator[str | ComplexityResult, None]:
        """Stream complexity analysis, yielding text chunks then final result.

        Yields:
            str: Raw text chunks from the LLM as they arrive.
            ComplexityResult: Final parsed result (last item yielded).
        """
        if not self.is_configured() or self._client is None:
            yield self._not_configured_result()
            return

        try:
            prompt = self._load_prompt_template().format(code=code)
            model, gen_config = self._build_gen_config()

            logger.info(f"Gemini streaming request: model={model}")

            with llm_span(
                "generate_content_stream",
                model,
                operation_type="complexity_analysis_stream",
                prompt_chars=len(prompt),
            ) as span:
                accumulated = ""
                chunk_count = 0
                last_chunk = None

                async for chunk in await self._client.aio.models.generate_content_stream(
                    model=model,
                    contents=prompt,
                    config=gen_config,
                ):
                    chunk_count += 1
                    last_chunk = chunk
                    text = chunk.text or ""
                    if text:
                        accumulated += text
                        yield text

                # Attach response attributes from the final chunk
                usage = last_chunk.usage_metadata if last_chunk else None
                add_llm_response_attributes(
                    span,
                    response_chars=len(accumulated),
                    response_truncated=accumulated[:200] if accumulated else None,
                    finish_reason=str(last_chunk.candidates[0].finish_reason)
                    if last_chunk and last_chunk.candidates
                    else None,
                    input_tokens=usage.prompt_token_count if usage else None,
                    output_tokens=usage.candidates_token_count if usage else None,
                    thinking_tokens=usage.thoughts_token_count if usage else None,
                    total_tokens=usage.total_token_count if usage else None,
                    stream_chunk_count=chunk_count,
                    response_id=getattr(last_chunk, "response_id", None) if last_chunk else None,
                    model_version=getattr(last_chunk, "model_version", None)
                    if last_chunk
                    else None,
                )

            logger.debug(f"Streaming complete, total chars: {len(accumulated)}")
            yield self._parse_response(accumulated, model=model)

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            yield ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                narrative="",
                error=str(e),
                model=self._model,
            )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_text: str, model: str | None = None) -> ComplexityResult:
        """Parse the Markdown narrative + trailing JSON block.

        The LLM responds with a Markdown analysis followed by a fenced
        JSON block containing ``{"time_complexity": "...", "space_complexity": "..."}``.

        Args:
            raw_text: Full response text from Gemini.
            model: The model name used for analysis.

        Returns:
            Parsed ComplexityResult.
        """
        matches = list(_JSON_BLOCK_RE.finditer(raw_text))

        if matches:
            last_match = matches[-1]
            json_str = last_match.group(1).strip()
            narrative = raw_text[: last_match.start()].strip()

            try:
                data = json.loads(json_str)
                return ComplexityResult(
                    time_complexity=data.get("time_complexity", "Unknown"),
                    space_complexity=data.get("space_complexity", "Unknown"),
                    narrative=narrative,
                    raw_response=raw_text,
                    model=model or self._model,
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON block: {e}")
                return ComplexityResult(
                    time_complexity="Unknown",
                    space_complexity="Unknown",
                    narrative=raw_text.strip(),
                    raw_response=raw_text,
                    error=f"JSON parse error: {e}",
                    model=model or self._model,
                )
        else:
            # Fallback: try extracting from ### headings
            time_match = _TIME_HEADING_RE.search(raw_text)
            space_match = _SPACE_HEADING_RE.search(raw_text)

            if time_match or space_match:
                logger.info("No JSON block found; extracted complexity from headings")
                return ComplexityResult(
                    time_complexity=time_match.group(1) if time_match else "Unknown",
                    space_complexity=space_match.group(1) if space_match else "Unknown",
                    narrative=raw_text.strip(),
                    raw_response=raw_text,
                    model=model or self._model,
                )

            logger.warning(
                "No JSON block or heading complexity found in LLM response: %s",
                repr(raw_text[:300]),
            )
            return ComplexityResult(
                time_complexity="Unknown",
                space_complexity="Unknown",
                narrative=raw_text.strip(),
                raw_response=raw_text,
                error="Could not extract complexity values from response",
                model=model or self._model,
            )


# Singleton instance
_provider: GeminiProvider | None = None


def get_gemini_provider() -> GeminiProvider:
    """Get or create the Gemini provider singleton."""
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider

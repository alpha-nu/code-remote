"""Cypher query generator using LLM Text-to-Cypher.

Generates Neo4j Cypher queries from natural language using Gemini LLM.
Includes validation to ensure generated queries are safe to execute.
"""

import logging
import re
from pathlib import Path

from google import genai
from google.genai import types

from common.config import settings
from common.tracing import add_llm_response_attributes, llm_span

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent.parent.parent / "analyzer" / "prompts" / "text_to_cypher.txt"


class CypherGenerator:
    """Generates Cypher queries from natural language using LLM."""

    # Forbidden keywords that indicate write operations
    FORBIDDEN_KEYWORDS = frozenset(
        [
            "CREATE",
            "DELETE",
            "SET",
            "MERGE",
            "REMOVE",
            "DROP",
            "DETACH",
            "CALL {",
            "FOREACH",
            "LOAD CSV",
        ]
    )

    # Required elements for security
    REQUIRED_ELEMENTS = ["$user_id"]

    def __init__(self, client: genai.Client | None = None):
        """Initialize the Cypher generator.

        Args:
            client: Optional Gemini client. If not provided, creates one.
        """
        self._client = client
        self._prompt_template: str | None = None

    @property
    def client(self) -> genai.Client:
        """Get the Gemini client."""
        if self._client is None:
            api_key = settings.resolved_gemini_api_key
            if not api_key:
                raise ValueError("Gemini API key not configured")
            self._client = genai.Client(api_key=api_key)
        return self._client

    @property
    def prompt_template(self) -> str:
        """Get the prompt template (loaded lazily)."""
        if self._prompt_template is None:
            self._prompt_template = self._load_prompt()
        return self._prompt_template

    def _load_prompt(self) -> str:
        """Load the Text-to-Cypher prompt template."""
        try:
            return PROMPT_PATH.read_text()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {PROMPT_PATH}")
            raise

    async def generate(self, user_query: str) -> str | None:
        """Generate a Cypher query from natural language.

        Args:
            user_query: The user's natural language search query.

        Returns:
            Generated Cypher query string, or None if generation fails.
        """
        try:
            prompt = self.prompt_template.format(user_query=user_query)

            # Config for generation (from settings)
            model = settings.resolved_llm_cypher_model
            temperature = settings.llm_cypher_temperature
            max_output_tokens = settings.llm_cypher_max_tokens

            # Generate with X-Ray tracing
            with llm_span(
                "generate_content",
                model,
                operation_type="text_to_cypher",
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                prompt_chars=len(prompt),
                user_query=user_query,
            ) as span:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    ),
                )

                raw_text = response.text.strip() if response.text else ""

                # Extract Cypher from response (may be in code block)
                cypher = self._extract_cypher(raw_text) if raw_text else None
                validated = cypher is not None and self.is_valid_cypher(cypher)

                # Add response attributes to span including token usage
                usage = response.usage_metadata
                add_llm_response_attributes(
                    span,
                    # Response info
                    response_chars=len(raw_text),
                    raw_response=raw_text[:300] if raw_text else None,
                    generated_cypher=cypher if cypher else None,
                    cypher_valid=validated,
                    finish_reason=str(response.candidates[0].finish_reason)
                    if response.candidates
                    else None,
                    # Token usage
                    input_tokens=usage.prompt_token_count if usage else None,
                    output_tokens=usage.candidates_token_count if usage else None,
                    thinking_tokens=usage.thoughts_token_count if usage else None,
                    total_tokens=usage.total_token_count if usage else None,
                    # Model info
                    response_id=response.response_id,
                    model_version=getattr(response, "model_version", None),
                )

            if not raw_text:
                logger.warning("Empty response from Cypher generator")
                return None

            if not cypher:
                logger.warning("Could not extract Cypher from response")
                return None

            if not validated:
                logger.warning(
                    "Generated Cypher failed validation",
                    extra={"cypher": cypher[:200]},
                )
                return None

            return cypher

        except Exception as e:
            logger.exception(f"Cypher generation failed: {e}")
            return None

    def _extract_cypher(self, response: str) -> str | None:
        """Extract Cypher query from LLM response.

        Handles responses that may be wrapped in markdown code blocks.

        Args:
            response: Raw LLM response text.

        Returns:
            Extracted Cypher query, or None if extraction fails.
        """
        # Try to extract from code block first
        code_block_pattern = r"```(?:cypher)?\s*([\s\S]*?)```"
        match = re.search(code_block_pattern, response)

        if match:
            return match.group(1).strip()

        # If no code block, assume the whole response is Cypher
        # Remove any leading/trailing whitespace
        cleaned = response.strip()

        # Basic sanity check - should start with MATCH or CALL
        if cleaned.upper().startswith(("MATCH", "CALL")):
            return cleaned

        return None

    def is_valid_cypher(self, cypher: str) -> bool:
        """Validate that generated Cypher is safe to execute.

        Checks:
        1. No write operations (CREATE, DELETE, SET, etc.)
        2. Contains required user filter
        3. Basic syntax sanity

        Args:
            cypher: The Cypher query to validate.

        Returns:
            True if query is safe to execute, False otherwise.
        """
        cypher_upper = cypher.upper()

        # Check for forbidden write operations
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Match as whole word to avoid false positives
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, cypher_upper):
                logger.warning(f"Cypher contains forbidden keyword: {keyword}")
                return False

        # Check for required elements
        for required in self.REQUIRED_ELEMENTS:
            if required not in cypher:
                logger.warning(f"Cypher missing required element: {required}")
                return False

        # Basic structure validation
        if not cypher_upper.strip().startswith(("MATCH", "CALL")):
            logger.warning("Cypher doesn't start with MATCH or CALL")
            return False

        return True


def get_cypher_generator() -> CypherGenerator:
    """Get a Cypher generator instance.

    Returns:
        CypherGenerator instance.
    """
    return CypherGenerator()

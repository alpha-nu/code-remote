"""Embedding service using Gemini embedding model.

Generates vector embeddings for semantic search.
"""

import logging

from google import genai
from google.genai import types

from common.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using Gemini."""

    def __init__(self, client: genai.Client | None = None):
        """Initialize embedding service.

        Args:
            client: Optional Gemini client. If not provided, creates one.
        """
        self._client = client

    @property
    def client(self) -> genai.Client:
        """Get the Gemini client."""
        if self._client is None:
            api_key = settings.resolved_gemini_api_key
            if not api_key:
                raise ValueError("Gemini API key not configured")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            768-dimension embedding vector.
        """
        model = f"models/{settings.gemini_embedding_model}"

        # Use embed_content for embedding generation with 768 dimensions
        response = self.client.models.embed_content(
            model=model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )

        # Extract embedding from response
        embedding = response.embeddings[0].values
        logger.debug(f"Generated embedding with {len(embedding)} dimensions")
        return list(embedding)

    def generate_embedding_sync(self, text: str) -> list[float]:
        """Generate embedding for text (synchronous version).

        Args:
            text: Text to embed.

        Returns:
            768-dimension embedding vector.
        """
        model = f"models/{settings.gemini_embedding_model}"

        response = self.client.models.embed_content(
            model=model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )

        embedding = response.embeddings[0].values
        logger.debug(f"Generated embedding with {len(embedding)} dimensions")
        return list(embedding)

    def build_snippet_embedding_input(
        self,
        title: str,
        code: str,
        time_complexity: str,
        space_complexity: str,
        description: str | None = None,
        complexity_explanation: str | None = None,
    ) -> str:
        """Build the text input for snippet embedding.

        Combines all searchable information about a snippet into a single
        text that will be embedded for semantic search.

        Args:
            title: Snippet title.
            code: Snippet code (will be truncated if too long).
            time_complexity: Time complexity notation.
            space_complexity: Space complexity notation.
            description: Optional user description.
            complexity_explanation: Optional LLM explanation.

        Returns:
            Combined text for embedding.
        """
        parts = []

        # 1. Title (primary identifier)
        parts.append(f"Title: {title}")

        # 2. Description (if provided)
        if description:
            parts.append(f"Description: {description}")

        # 3. Analysis summary (critical for semantic search)
        analysis_lines = ["Analysis:"]
        analysis_lines.append(
            f"- Time Complexity: {time_complexity} ({self._complexity_name(time_complexity)})"
        )
        analysis_lines.append(
            f"- Space Complexity: {space_complexity} ({self._complexity_name(space_complexity)})"
        )
        if complexity_explanation:
            analysis_lines.append(f"- Explanation: {complexity_explanation}")
        parts.append("\n".join(analysis_lines))

        # 4. Code (truncated to ~8000 chars to stay within token limits)
        truncated_code = code[:8000]
        if len(code) > 8000:
            truncated_code += "\n... (truncated)"
        parts.append(f"Code:\n{truncated_code}")

        return "\n\n".join(parts)

    def _complexity_name(self, notation: str) -> str:
        """Get human-readable name for complexity notation.

        Args:
            notation: Complexity notation (e.g., "O(n²)").

        Returns:
            Human-readable name (e.g., "quadratic").
        """
        names = {
            "O(1)": "constant",
            "O(log n)": "logarithmic",
            "O(n)": "linear",
            "O(n log n)": "linearithmic",
            "O(n²)": "quadratic",
            "O(n³)": "cubic",
            "O(2^n)": "exponential",
            "O(n!)": "factorial",
        }
        return names.get(notation, "unknown")


# Singleton instance
_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service

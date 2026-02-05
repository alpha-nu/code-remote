"""Unit tests for the embedding service."""

from unittest.mock import MagicMock

import pytest


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Gemini client."""
        client = MagicMock()
        # Mock the embedding response structure
        embedding_result = MagicMock()
        embedding_result.values = [0.1] * 768
        response = MagicMock()
        response.embeddings = [embedding_result]
        client.models.embed_content.return_value = response
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create an EmbeddingService with mocked client."""
        from api.services.embedding_service import EmbeddingService

        return EmbeddingService(client=mock_client)

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_vector(self, service):
        """Test that generate_embedding returns a 768-dim vector."""
        result = await service.generate_embedding("test text")

        assert isinstance(result, list)
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_generate_embedding_calls_model(self, service, mock_client):
        """Test that the correct model is called."""
        await service.generate_embedding("hello world")

        mock_client.models.embed_content.assert_called_once()
        call_kwargs = mock_client.models.embed_content.call_args[1]
        assert "text-embedding-004" in call_kwargs["model"]
        assert call_kwargs["contents"] == "hello world"

    def test_generate_embedding_sync_returns_vector(self, service):
        """Test synchronous embedding generation."""
        result = service.generate_embedding_sync("test text")

        assert isinstance(result, list)
        assert len(result) == 768


class TestBuildSnippetEmbeddingInput:
    """Tests for building snippet embedding input."""

    @pytest.fixture
    def service(self):
        """Create an EmbeddingService."""
        from api.services.embedding_service import EmbeddingService

        return EmbeddingService(client=MagicMock())

    def test_includes_title(self, service):
        """Test that title is included in embedding input."""
        result = service.build_snippet_embedding_input(
            title="Binary Search",
            code="def search(): pass",
            time_complexity="O(log n)",
            space_complexity="O(1)",
        )

        assert "Title: Binary Search" in result

    def test_includes_description_when_provided(self, service):
        """Test that description is included when provided."""
        result = service.build_snippet_embedding_input(
            title="Test",
            code="pass",
            time_complexity="O(n)",
            space_complexity="O(1)",
            description="A test description",
        )

        assert "Description: A test description" in result

    def test_excludes_description_when_none(self, service):
        """Test that description section is excluded when None."""
        result = service.build_snippet_embedding_input(
            title="Test",
            code="pass",
            time_complexity="O(n)",
            space_complexity="O(1)",
            description=None,
        )

        assert "Description:" not in result

    def test_includes_complexity_analysis(self, service):
        """Test that complexity analysis is included."""
        result = service.build_snippet_embedding_input(
            title="Sort",
            code="pass",
            time_complexity="O(n²)",
            space_complexity="O(n)",
        )

        assert "Time Complexity: O(n²)" in result
        assert "quadratic" in result
        assert "Space Complexity: O(n)" in result
        assert "linear" in result

    def test_includes_code(self, service):
        """Test that code is included."""
        result = service.build_snippet_embedding_input(
            title="Test",
            code="def my_function():\n    return 42",
            time_complexity="O(1)",
            space_complexity="O(1)",
        )

        assert "Code:" in result
        assert "def my_function():" in result
        assert "return 42" in result

    def test_truncates_long_code(self, service):
        """Test that long code is truncated."""
        long_code = "x = 1\n" * 5000  # Very long code
        result = service.build_snippet_embedding_input(
            title="Test",
            code=long_code,
            time_complexity="O(1)",
            space_complexity="O(1)",
        )

        # Should be truncated to ~8000 chars + "truncated" marker
        assert "... (truncated)" in result
        assert len(result) < len(long_code) + 500

    def test_includes_explanation_when_provided(self, service):
        """Test that complexity explanation is included when provided."""
        result = service.build_snippet_embedding_input(
            title="Test",
            code="pass",
            time_complexity="O(n)",
            space_complexity="O(1)",
            complexity_explanation="Uses a single loop over the input.",
        )

        assert "Explanation: Uses a single loop over the input." in result

    def test_structure_for_semantic_search(self, service):
        """Test that all parts are joined properly for semantic search."""
        result = service.build_snippet_embedding_input(
            title="Binary Search",
            code="def binary_search(arr, target): pass",
            time_complexity="O(log n)",
            space_complexity="O(1)",
            description="Efficient search for sorted arrays",
            complexity_explanation="Divides search space in half each iteration",
        )

        # Check structure
        assert result.startswith("Title: Binary Search")
        assert "Description:" in result
        assert "Analysis:" in result
        assert "Code:" in result

        # Check semantic terms that should match searches
        assert "logarithmic" in result
        assert "constant" in result


class TestComplexityName:
    """Tests for complexity notation to name mapping."""

    @pytest.fixture
    def service(self):
        """Create an EmbeddingService."""
        from api.services.embedding_service import EmbeddingService

        return EmbeddingService(client=MagicMock())

    def test_all_complexity_names(self, service):
        """Test all complexity notations map to correct names."""
        mappings = {
            "O(1)": "constant",
            "O(log n)": "logarithmic",
            "O(n)": "linear",
            "O(n log n)": "linearithmic",
            "O(n²)": "quadratic",
            "O(n³)": "cubic",
            "O(2^n)": "exponential",
            "O(n!)": "factorial",
        }

        for notation, expected_name in mappings.items():
            result = service._complexity_name(notation)
            assert result == expected_name, f"Expected {expected_name} for {notation}"

    def test_unknown_complexity_returns_unknown(self, service):
        """Test that unknown complexity returns 'unknown'."""
        result = service._complexity_name("O(n^4)")
        assert result == "unknown"

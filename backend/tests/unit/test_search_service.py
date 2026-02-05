"""Unit tests for the search service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.search_service import SearchResult, SearchService


class TestSearchService:
    """Tests for SearchService."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j service."""
        mock = MagicMock()
        mock.execute_query = MagicMock()
        return mock

    @pytest.fixture
    def mock_embedding(self):
        """Create a mock embedding service."""
        mock = MagicMock()
        mock.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        return mock

    @pytest.fixture
    def mock_cypher_gen(self):
        """Create a mock Cypher generator."""
        mock = MagicMock()
        mock.generate = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_neo4j, mock_embedding, mock_cypher_gen):
        """Create a SearchService with mocked dependencies."""
        return SearchService(
            neo4j_service=mock_neo4j,
            embedding_service=mock_embedding,
            cypher_generator=mock_cypher_gen,
        )

    @pytest.mark.asyncio
    async def test_search_uses_cypher_when_successful(self, service, mock_neo4j, mock_cypher_gen):
        """Test that successful Text-to-Cypher results use cypher method."""
        mock_cypher_gen.generate.return_value = "MATCH (s) WHERE $user_id RETURN s"
        mock_neo4j.execute_query.return_value = [{"snippet_id": "1", "title": "Test", "score": 0.9}]

        result = await service.search("sorting algorithms", "user-123", limit=10)

        assert result.method == "cypher"
        assert len(result.results) == 1
        assert result.total == 1
        mock_cypher_gen.generate.assert_called_once_with("sorting algorithms")

    @pytest.mark.asyncio
    async def test_search_falls_back_on_cypher_generation_failure(
        self, service, mock_neo4j, mock_cypher_gen
    ):
        """Test fallback to semantic when Cypher generation fails."""
        mock_cypher_gen.generate.return_value = None
        mock_neo4j.execute_query.return_value = [
            {"snippet_id": "1", "title": "Result", "score": 0.85}
        ]

        result = await service.search("find code", "user-123")

        assert result.method == "semantic"
        # Should have called execute_query with FALLBACK_CYPHER
        assert mock_neo4j.execute_query.called

    @pytest.mark.asyncio
    async def test_search_falls_back_on_empty_cypher_results(
        self, service, mock_neo4j, mock_cypher_gen
    ):
        """Test fallback when Cypher query returns no results."""
        mock_cypher_gen.generate.return_value = "MATCH (s) WHERE $user_id RETURN s"
        # First call (Cypher) returns empty, second call (fallback) returns results
        mock_neo4j.execute_query.side_effect = [
            [],  # Cypher result
            [{"snippet_id": "2", "title": "Fallback", "score": 0.8}],  # Semantic fallback
        ]

        result = await service.search("rare query", "user-123")

        assert result.method == "semantic"
        assert len(result.results) == 1
        assert mock_neo4j.execute_query.call_count == 2

    @pytest.mark.asyncio
    async def test_search_falls_back_on_cypher_execution_error(
        self, service, mock_neo4j, mock_cypher_gen
    ):
        """Test fallback when Cypher execution throws an error."""
        mock_cypher_gen.generate.return_value = "MATCH (s) WHERE $user_id RETURN s"
        # First call throws, second call succeeds
        mock_neo4j.execute_query.side_effect = [
            Exception("Cypher error"),
            [{"snippet_id": "3", "title": "Safe", "score": 0.75}],
        ]

        result = await service.search("query", "user-123")

        assert result.method == "semantic"
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_embedding_failure(self, service, mock_embedding):
        """Test that embedding failure returns empty results."""
        mock_embedding.generate_embedding.return_value = None

        result = await service.search("query", "user-123")

        assert result.results == []
        assert result.method == "semantic"
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_search_always_generates_embedding_first(
        self, service, mock_embedding, mock_cypher_gen, mock_neo4j
    ):
        """Test that embedding is generated before Cypher (for fallback readiness)."""
        mock_cypher_gen.generate.return_value = "MATCH ... $user_id ..."
        mock_neo4j.execute_query.return_value = [{"id": "1"}]

        await service.search("test query", "user-123")

        # Embedding should be generated
        mock_embedding.generate_embedding.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_passes_correct_params(
        self, service, mock_neo4j, mock_cypher_gen, mock_embedding
    ):
        """Test that correct parameters are passed to Neo4j."""
        mock_cypher_gen.generate.return_value = "MATCH (s) WHERE $user_id RETURN s"
        mock_neo4j.execute_query.return_value = [{"id": "1"}]

        await service.search("query", "user-456", limit=5)

        # Check the params passed to execute_query
        call_args = mock_neo4j.execute_query.call_args
        params = call_args[0][1]  # Second positional arg
        assert params["user_id"] == "user-456"
        assert params["limit"] == 5
        assert len(params["query_embedding"]) == 768


class TestFindSimilar:
    """Tests for find_similar functionality."""

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j service."""
        mock = MagicMock()
        mock.execute_query = MagicMock()
        return mock

    @pytest.fixture
    def mock_embedding(self):
        """Create a mock embedding service."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def mock_cypher_gen(self):
        """Create a mock Cypher generator."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_neo4j, mock_embedding, mock_cypher_gen):
        """Create a SearchService with mocked dependencies."""
        return SearchService(
            neo4j_service=mock_neo4j,
            embedding_service=mock_embedding,
            cypher_generator=mock_cypher_gen,
        )

    @pytest.mark.asyncio
    async def test_find_similar_returns_results(self, service, mock_neo4j):
        """Test that find_similar returns matching snippets."""
        mock_neo4j.execute_query.return_value = [
            {"snippet_id": "2", "title": "Similar 1", "score": 0.95},
            {"snippet_id": "3", "title": "Similar 2", "score": 0.88},
        ]

        results = await service.find_similar(
            snippet_id="snippet-1",
            user_id="user-123",
            limit=5,
        )

        assert len(results) == 2
        assert results[0]["snippet_id"] == "2"
        mock_neo4j.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_passes_correct_params(self, service, mock_neo4j):
        """Test that correct parameters are passed to Neo4j."""
        mock_neo4j.execute_query.return_value = []

        await service.find_similar(
            snippet_id="snippet-abc",
            user_id="user-xyz",
            limit=3,
        )

        call_args = mock_neo4j.execute_query.call_args
        params = call_args[0][1]
        assert params["snippet_id"] == "snippet-abc"
        assert params["user_id"] == "user-xyz"
        assert params["limit"] == 3
        assert params["search_limit"] == 4  # limit + 1

    @pytest.mark.asyncio
    async def test_find_similar_handles_errors(self, service, mock_neo4j):
        """Test that errors return empty list."""
        mock_neo4j.execute_query.side_effect = Exception("Neo4j error")

        results = await service.find_similar(
            snippet_id="snippet-1",
            user_id="user-123",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_find_similar_returns_empty_on_no_results(self, service, mock_neo4j):
        """Test that no matches returns empty list."""
        mock_neo4j.execute_query.return_value = None

        results = await service.find_similar(
            snippet_id="snippet-1",
            user_id="user-123",
        )

        assert results == []


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_attributes(self):
        """Test SearchResult has correct attributes."""
        result = SearchResult(
            results=[{"id": "1", "title": "Test"}],
            query="search term",
            method="cypher",
            total=1,
        )

        assert result.results == [{"id": "1", "title": "Test"}]
        assert result.query == "search term"
        assert result.method == "cypher"
        assert result.total == 1

    def test_search_result_semantic_method(self):
        """Test SearchResult with semantic method."""
        result = SearchResult(
            results=[],
            query="test",
            method="semantic",
            total=0,
        )

        assert result.method == "semantic"

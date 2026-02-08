"""Unit tests for the Cypher generator service."""

from unittest.mock import MagicMock, patch

import pytest


class TestCypherValidation:
    """Tests for Cypher validation logic."""

    @pytest.fixture
    def generator(self):
        """Create a CypherGenerator with mocked dependencies."""
        from api.services.cypher_generator import CypherGenerator

        mock_client = MagicMock()
        gen = CypherGenerator(client=mock_client)
        gen._prompt_template = "test prompt {user_query}"
        return gen

    def test_valid_read_query(self, generator):
        """Test that valid read queries pass validation."""
        valid_query = """
        MATCH (s:Snippet)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, s.title
        ORDER BY s.updated_at DESC
        LIMIT 10
        """
        assert generator.is_valid_cypher(valid_query) is True

    def test_valid_vector_search_query(self, generator):
        """Test that vector search queries pass validation."""
        valid_query = """
        CALL db.index.vector.queryNodes('snippet_embedding', 10, $query_embedding)
        YIELD node AS s, score
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, s.title, score
        ORDER BY score DESC
        """
        assert generator.is_valid_cypher(valid_query) is True

    def test_combined_vector_and_graph_query(self, generator):
        """Test that combined vector + graph queries pass validation."""
        valid_query = """
        CALL db.index.vector.queryNodes('snippet_embedding', 30, $query_embedding)
        YIELD node AS s, score
        MATCH (s)-[:HAS_TIME_COMPLEXITY]->(c:Complexity)
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, s.title, c.notation, score
        ORDER BY score DESC
        LIMIT 10
        """
        assert generator.is_valid_cypher(valid_query) is True

    def test_blocks_create_operations(self, generator):
        """Test that CREATE operations are blocked."""
        query = """
        CREATE (s:Snippet {id: '123', title: 'Test'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_delete_operations(self, generator):
        """Test that DELETE operations are blocked."""
        query = """
        MATCH (s:Snippet {id: '123'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        DELETE s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_set_operations(self, generator):
        """Test that SET operations are blocked."""
        query = """
        MATCH (s:Snippet {id: '123'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        SET s.title = 'Hacked'
        RETURN s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_merge_operations(self, generator):
        """Test that MERGE operations are blocked."""
        query = """
        MERGE (s:Snippet {id: '123'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_remove_operations(self, generator):
        """Test that REMOVE operations are blocked."""
        query = """
        MATCH (s:Snippet {id: '123'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        REMOVE s.title
        RETURN s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_drop_operations(self, generator):
        """Test that DROP operations are blocked."""
        query = """
        DROP INDEX snippet_embedding
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        """
        assert generator.is_valid_cypher(query) is False

    def test_blocks_detach_delete(self, generator):
        """Test that DETACH DELETE operations are blocked."""
        query = """
        MATCH (s:Snippet {id: '123'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        DETACH DELETE s
        """
        assert generator.is_valid_cypher(query) is False

    def test_requires_user_id_filter(self, generator):
        """Test that queries without user_id filter are rejected."""
        query = """
        MATCH (s:Snippet)
        RETURN s.id, s.title
        LIMIT 10
        """
        assert generator.is_valid_cypher(query) is False

    def test_case_insensitive_keyword_detection(self, generator):
        """Test that forbidden keywords are detected case-insensitively."""
        queries = [
            "create (s:Snippet {id: '1'}) MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id}) RETURN s",
            "DELETE (s) MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})",
            "Set s.x = 1 MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id}) RETURN s",
        ]
        for query in queries:
            assert generator.is_valid_cypher(query) is False


class TestCypherExtraction:
    """Tests for Cypher extraction from LLM responses."""

    @pytest.fixture
    def generator(self):
        """Create a CypherGenerator with mocked dependencies."""
        from api.services.cypher_generator import CypherGenerator

        mock_client = MagicMock()
        gen = CypherGenerator(client=mock_client)
        gen._prompt_template = "test prompt {user_query}"
        return gen

    def test_extract_from_code_block(self, generator):
        """Test extraction from markdown code block."""
        response = """
        Here's the query:
        ```cypher
        MATCH (s:Snippet)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        ```
        """
        result = generator._extract_cypher(response)
        assert result is not None
        assert "MATCH" in result
        assert "$user_id" in result

    def test_extract_from_code_block_no_language(self, generator):
        """Test extraction from code block without language specifier."""
        response = """
        ```
        MATCH (s:Snippet)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        ```
        """
        result = generator._extract_cypher(response)
        assert result is not None
        assert "MATCH" in result

    def test_extract_raw_cypher(self, generator):
        """Test extraction when response is raw Cypher."""
        response = """MATCH (s:Snippet)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, s.title
        ORDER BY s.updated_at DESC"""
        result = generator._extract_cypher(response)
        assert result is not None
        assert "MATCH" in result

    def test_extract_call_query(self, generator):
        """Test extraction of CALL-based queries."""
        response = """CALL db.index.vector.queryNodes('snippet_embedding', 10, $query_embedding)
        YIELD node AS s, score
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, score"""
        result = generator._extract_cypher(response)
        assert result is not None
        assert "CALL" in result

    def test_extract_returns_none_for_invalid(self, generator):
        """Test that invalid responses return None."""
        response = "I don't understand the query."
        result = generator._extract_cypher(response)
        assert result is None


class TestCypherGeneration:
    """Tests for the full generation flow."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with LLM configuration."""
        with patch("api.services.cypher_generator.settings") as mock:
            mock.resolved_llm_cypher_model = "gemini-2.5-flash"
            mock.resolved_llm_cypher_temperature = 0.1
            mock.resolved_llm_cypher_max_tokens = 500
            yield mock

    @pytest.fixture
    def mock_client(self):
        """Create a mock Gemini client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def generator(self, mock_client):
        """Create a CypherGenerator with mocked client."""
        from api.services.cypher_generator import CypherGenerator

        gen = CypherGenerator(client=mock_client)
        gen._prompt_template = "test prompt {user_query}"
        return gen

    @pytest.mark.asyncio
    async def test_generate_returns_valid_cypher(self, mock_settings, generator, mock_client):
        """Test successful Cypher generation."""
        mock_response = MagicMock()
        mock_response.text = """
        MATCH (s:Snippet)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s.id, s.title
        """
        mock_client.models.generate_content.return_value = mock_response

        result = await generator.generate("show my snippets")

        assert result is not None
        assert "MATCH" in result
        assert "$user_id" in result

    @pytest.mark.asyncio
    async def test_generate_returns_none_for_empty_response(
        self, mock_settings, generator, mock_client
    ):
        """Test that empty LLM response returns None."""
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        result = await generator.generate("find sorting")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_returns_none_for_invalid_cypher(
        self, mock_settings, generator, mock_client
    ):
        """Test that invalid Cypher (missing user_id) returns None."""
        mock_response = MagicMock()
        mock_response.text = """
        MATCH (s:Snippet)
        RETURN s.id, s.title
        """
        mock_client.models.generate_content.return_value = mock_response

        result = await generator.generate("show all snippets")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_returns_none_for_write_operations(
        self, mock_settings, generator, mock_client
    ):
        """Test that write operations are rejected."""
        mock_response = MagicMock()
        mock_response.text = """
        CREATE (s:Snippet {title: 'Evil'})
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        RETURN s
        """
        mock_client.models.generate_content.return_value = mock_response

        result = await generator.generate("create a snippet")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_handles_exceptions(self, mock_settings, generator, mock_client):
        """Test that exceptions are handled gracefully."""
        mock_client.models.generate_content.side_effect = Exception("API error")

        result = await generator.generate("search query")

        assert result is None

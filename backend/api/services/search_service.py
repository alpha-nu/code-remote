"""Search service for unified semantic and graph search.

Implements Text-to-Cypher with fallback to pure semantic search.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from api.services.cypher_generator import CypherGenerator, get_cypher_generator
from api.services.embedding_service import EmbeddingService
from api.services.neo4j_service import Neo4jService, get_neo4j_driver

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a search operation."""

    results: list[dict[str, Any]]
    query: str
    method: Literal["cypher", "semantic"]
    total: int


class SearchService:
    """Unified search service with Text-to-Cypher and semantic fallback."""

    # Fallback query - pure semantic similarity
    FALLBACK_CYPHER = """
    CALL db.index.vector.queryNodes('snippet_embedding', $limit, $query_embedding)
    YIELD node AS s, score
    MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
    MATCH (s)-[:HAS_TIME_COMPLEXITY]->(tc:Complexity)
    MATCH (s)-[:HAS_SPACE_COMPLEXITY]->(sc:Complexity)
    OPTIONAL MATCH (s)-[:WRITTEN_IN]->(l:Language)
    RETURN s.id AS snippet_id, s.title AS title, s.description AS description,
           tc.notation AS time_complexity,
           sc.notation AS space_complexity,
           l.name AS language,
           score
    ORDER BY score DESC
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        embedding_service: EmbeddingService,
        cypher_generator: CypherGenerator,
    ):
        """Initialize search service.

        Args:
            neo4j_service: Neo4j service for executing queries.
            embedding_service: Embedding service for generating query vectors.
            cypher_generator: Cypher generator for Text-to-Cypher.
        """
        self._neo4j = neo4j_service
        self._embedding = embedding_service
        self._cypher_gen = cypher_generator

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
    ) -> SearchResult:
        """Perform unified search with Text-to-Cypher and fallback.

        1. Generate query embedding (always, needed for fallback)
        2. Try LLM-generated Cypher
        3. If fails or no results, fall back to pure semantic search

        Args:
            query: Natural language search query.
            user_id: UUID of the current user.
            limit: Maximum number of results.

        Returns:
            SearchResult with matches and method used.
        """
        # 1. ALWAYS generate embedding first (needed for fallback anyway)
        query_embedding = await self._embedding.generate_embedding(query)

        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return SearchResult(
                results=[],
                query=query,
                method="semantic",
                total=0,
            )

        params = {
            "user_id": user_id,
            "query_embedding": query_embedding,
            "limit": limit,
        }

        # 2. Try LLM-generated Cypher
        try:
            cypher = await self._cypher_gen.generate(query)

            if cypher:
                results = await asyncio.to_thread(self._neo4j.execute_query, cypher, params)

                if results:  # Has results
                    return SearchResult(
                        results=results,
                        query=query,
                        method="cypher",
                        total=len(results),
                    )
                else:
                    logger.info(
                        "Text-to-Cypher returned no results, falling back",
                        extra={"query": query},
                    )
        except Exception as e:
            logger.warning(f"Text-to-Cypher failed: {e}")

        # 3. FALLBACK: Pure semantic search
        try:
            results = await asyncio.to_thread(
                self._neo4j.execute_query, self.FALLBACK_CYPHER, params
            )

            return SearchResult(
                results=results or [],
                query=query,
                method="semantic",
                total=len(results) if results else 0,
            )
        except Exception as e:
            logger.error(f"Semantic fallback failed: {e}")
            return SearchResult(
                results=[],
                query=query,
                method="semantic",
                total=0,
            )

    async def find_similar(
        self,
        snippet_id: str,
        user_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find snippets similar to a given snippet.

        Args:
            snippet_id: UUID of the source snippet.
            user_id: UUID of the current user.
            limit: Maximum number of similar snippets.

        Returns:
            List of similar snippet dictionaries.
        """
        query = """
        MATCH (source:Snippet {id: $snippet_id})
        CALL db.index.vector.queryNodes(
            'snippet_embedding',
            $search_limit,
            source.embedding
        )
        YIELD node AS s, score
        WHERE s.id <> $snippet_id
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        MATCH (s)-[:HAS_TIME_COMPLEXITY]->(tc:Complexity)
        OPTIONAL MATCH (s)-[:WRITTEN_IN]->(l:Language)
        RETURN s.id AS snippet_id, s.title AS title, s.description AS description,
               tc.notation AS time_complexity,
               l.name AS language,
               score
        ORDER BY score DESC
        LIMIT $limit
        """

        params = {
            "snippet_id": snippet_id,
            "user_id": user_id,
            "search_limit": limit + 1,  # +1 to account for excluding self
            "limit": limit,
        }

        try:
            results = await asyncio.to_thread(self._neo4j.execute_query, query, params)
            return results or []
        except Exception as e:
            logger.error(f"Find similar failed: {e}")
            return []


def get_search_service() -> SearchService:
    """Get a search service instance.

    Returns:
        SearchService configured with dependencies.
    """
    driver = get_neo4j_driver()
    return SearchService(
        neo4j_service=Neo4jService(driver),
        embedding_service=EmbeddingService(),
        cypher_generator=get_cypher_generator(),
    )

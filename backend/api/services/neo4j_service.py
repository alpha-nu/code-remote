"""Neo4j database service for graph operations."""

import json
import logging
from contextlib import contextmanager
from typing import Any

from neo4j import Driver, GraphDatabase

from common.config import get_secret_from_aws, settings

logger = logging.getLogger(__name__)


def get_neo4j_credentials() -> dict[str, str]:
    """Get Neo4j credentials from settings or AWS Secrets Manager.

    Returns:
        Dictionary with uri, username, password, and database.
    """
    # Try direct settings first
    if settings.neo4j_uri and settings.neo4j_password:
        return {
            "uri": settings.neo4j_uri,
            "username": settings.neo4j_username,
            "password": settings.neo4j_password,
            "database": settings.neo4j_database,
        }

    # Fall back to AWS Secrets Manager
    if settings.neo4j_secret_arn:
        secret_string = get_secret_from_aws(settings.neo4j_secret_arn)
        if secret_string:
            try:
                secret_data = json.loads(secret_string)
                return {
                    "uri": secret_data.get("uri", ""),
                    "username": secret_data.get("username", "neo4j"),
                    "password": secret_data.get("password", ""),
                    "database": secret_data.get("database", "neo4j"),
                }
            except json.JSONDecodeError:
                logger.error("Failed to parse Neo4j secret as JSON")

    return {
        "uri": "",
        "username": "neo4j",
        "password": "",
        "database": "neo4j",
    }


# Global driver instance (singleton for high-throughput handlers)
_driver: Driver | None = None

# Connection pool size - 1 for Lambda (single concurrent request per container)
_MAX_CONNECTION_POOL_SIZE = 1


def get_neo4j_driver() -> Driver:
    """Get or create the Neo4j driver singleton.

    Use this for high-throughput handlers (sync-worker, API routes) where
    driver creation overhead would impact performance. The singleton survives
    Lambda container reuse.

    IMPORTANT: Never close this driver - it's shared across invocations.

    Returns:
        Neo4j Driver instance.

    Raises:
        ValueError: If Neo4j credentials are not configured.
    """
    global _driver

    if _driver is not None:
        return _driver

    credentials = get_neo4j_credentials()

    if not credentials["uri"] or not credentials["password"]:
        raise ValueError(
            "Neo4j credentials not configured. "
            "Set NEO4J_URI and NEO4J_PASSWORD or NEO4J_SECRET_ARN."
        )

    _driver = GraphDatabase.driver(
        credentials["uri"],
        auth=(credentials["username"], credentials["password"]),
        max_connection_pool_size=_MAX_CONNECTION_POOL_SIZE,
    )

    # Verify connectivity
    _driver.verify_connectivity()
    logger.info(f"Connected to Neo4j at {credentials['uri']}")

    return _driver


@contextmanager
def neo4j_driver_context():
    """Context manager for short-lived Neo4j driver usage.

    Use this for one-off operations like migrations where you want
    explicit cleanup. Creates a fresh driver and closes it on exit.

    Usage:
        with neo4j_driver_context() as driver:
            # use driver
        # driver is closed automatically

    Yields:
        Neo4j Driver instance.

    Raises:
        ValueError: If Neo4j credentials are not configured.
    """
    credentials = get_neo4j_credentials()

    if not credentials["uri"] or not credentials["password"]:
        raise ValueError(
            "Neo4j credentials not configured. "
            "Set NEO4J_URI and NEO4J_PASSWORD or NEO4J_SECRET_ARN."
        )

    driver = GraphDatabase.driver(
        credentials["uri"],
        auth=(credentials["username"], credentials["password"]),
        max_connection_pool_size=_MAX_CONNECTION_POOL_SIZE,
    )

    try:
        driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {credentials['uri']} (context manager)")
        yield driver
    finally:
        driver.close()
        logger.info("Neo4j driver closed (context manager)")


def close_neo4j_driver() -> None:
    """Close the Neo4j driver singleton and release resources.

    WARNING: Only call this at application shutdown. Never call in Lambda
    handlers - the singleton should survive container reuse.

    For short-lived operations, use neo4j_driver_context() instead.
    """
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver singleton closed")


@contextmanager
def get_neo4j_session():
    """Context manager for Neo4j session.

    Yields:
        Neo4j Session instance.
    """
    driver = get_neo4j_driver()
    credentials = get_neo4j_credentials()
    session = driver.session(database=credentials["database"])
    try:
        yield session
    finally:
        session.close()


class Neo4jService:
    """Service for Neo4j graph operations."""

    def __init__(self, driver: Driver | None = None):
        """Initialize Neo4j service.

        Args:
            driver: Optional driver instance. If not provided, uses global driver.
        """
        self._driver = driver

    @property
    def driver(self) -> Driver:
        """Get the Neo4j driver."""
        if self._driver is None:
            self._driver = get_neo4j_driver()
        return self._driver

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.

        Args:
            query: Cypher query string.
            parameters: Query parameters.
            database: Database name. Defaults to configured database.

        Returns:
            List of result records as dictionaries.
        """
        if database is None:
            credentials = get_neo4j_credentials()
            database = credentials["database"]

        with self.driver.session(database=database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write Cypher query in a transaction.

        Args:
            query: Cypher query string.
            parameters: Query parameters.
            database: Database name. Defaults to configured database.

        Returns:
            List of result records as dictionaries.
        """
        if database is None:
            credentials = get_neo4j_credentials()
            database = credentials["database"]

        def _execute_tx(tx):
            result = tx.run(query, parameters or {})
            return [record.data() for record in result]

        with self.driver.session(database=database) as session:
            return session.execute_write(_execute_tx)

    def upsert_snippet(
        self,
        snippet_id: str,
        user_id: str,
        title: str,
        code: str,
        language: str,
        time_complexity: str,
        space_complexity: str,
        embedding: list[float],
        description: str | None = None,
        complexity_explanation: str | None = None,
    ) -> dict[str, Any]:
        """Upsert a snippet node with all relationships.

        Args:
            snippet_id: UUID of the snippet.
            user_id: UUID of the owner.
            title: Snippet title.
            code: Snippet code.
            language: Programming language.
            time_complexity: Time complexity notation (e.g., "O(n)").
            space_complexity: Space complexity notation.
            embedding: Vector embedding (768 dimensions).
            description: Optional description.
            complexity_explanation: Optional LLM explanation.

        Returns:
            The upserted snippet data.
        """
        query = """
        // Ensure user exists
        MERGE (u:User {id: $user_id})

        // Upsert snippet
        MERGE (s:Snippet {id: $snippet_id})
        ON CREATE SET s.created_at = datetime()
        SET s.title = $title,
            s.description = $description,
            s.code = $code,
            s.complexity_explanation = $complexity_explanation,
            s.embedding = $embedding,
            s.updated_at = datetime(),
            s.synced_at = datetime()

        // Link to user
        MERGE (s)-[:OWNED_BY]->(u)

        // Link to language
        WITH s
        MATCH (l:Language {name: $language})
        MERGE (s)-[:WRITTEN_IN]->(l)

        // Update time complexity (remove old, add new)
        WITH s
        OPTIONAL MATCH (s)-[r1:HAS_TIME_COMPLEXITY]->()
        DELETE r1
        WITH s
        MATCH (tc:Complexity {notation: $time_complexity})
        MERGE (s)-[:HAS_TIME_COMPLEXITY]->(tc)

        // Update space complexity (remove old, add new)
        WITH s
        OPTIONAL MATCH (s)-[r2:HAS_SPACE_COMPLEXITY]->()
        DELETE r2
        WITH s
        MATCH (sc:Complexity {notation: $space_complexity})
        MERGE (s)-[:HAS_SPACE_COMPLEXITY]->(sc)

        RETURN s.id AS id, s.title AS title, s.synced_at AS synced_at
        """

        results = self.execute_write(
            query,
            {
                "snippet_id": snippet_id,
                "user_id": user_id,
                "title": title,
                "description": description,
                "code": code,
                "complexity_explanation": complexity_explanation,
                "embedding": embedding,
                "language": language,
                "time_complexity": time_complexity,
                "space_complexity": space_complexity,
            },
        )

        return results[0] if results else {}

    def delete_snippet(self, snippet_id: str) -> bool:
        """Delete a snippet node and all its relationships.

        Args:
            snippet_id: UUID of the snippet to delete.

        Returns:
            True if deleted, False if not found.
        """
        query = """
        MATCH (s:Snippet {id: $snippet_id})
        DETACH DELETE s
        RETURN count(s) AS deleted
        """

        results = self.execute_write(query, {"snippet_id": snippet_id})
        return results[0]["deleted"] > 0 if results else False

    def search_by_embedding(
        self,
        query_embedding: list[float],
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search snippets by semantic similarity.

        Args:
            query_embedding: Query vector (768 dimensions).
            user_id: Filter by owner.
            limit: Maximum results.

        Returns:
            List of matching snippets with scores.
        """
        query = """
        CALL db.index.vector.queryNodes('snippet_embedding', $limit, $query_embedding)
        YIELD node AS s, score
        MATCH (s)-[:OWNED_BY]->(u:User {id: $user_id})
        MATCH (s)-[:HAS_TIME_COMPLEXITY]->(tc:Complexity)
        MATCH (s)-[:HAS_SPACE_COMPLEXITY]->(sc:Complexity)
        OPTIONAL MATCH (s)-[:WRITTEN_IN]->(l:Language)
        RETURN s.id AS id,
               s.title AS title,
               s.description AS description,
               tc.notation AS time_complexity,
               sc.notation AS space_complexity,
               l.name AS language,
               score
        ORDER BY score DESC
        """

        return self.execute_query(
            query,
            {
                "query_embedding": query_embedding,
                "user_id": user_id,
                "limit": limit,
            },
        )

    def get_snippets_by_complexity(
        self,
        user_id: str,
        time_complexity: str | None = None,
        space_complexity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get snippets filtered by complexity.

        Args:
            user_id: Filter by owner.
            time_complexity: Optional time complexity filter.
            space_complexity: Optional space complexity filter.
            limit: Maximum results.

        Returns:
            List of matching snippets.
        """
        conditions = ["(s)-[:OWNED_BY]->(u:User {id: $user_id})"]
        params: dict[str, Any] = {"user_id": user_id, "limit": limit}

        if time_complexity:
            conditions.append("(s)-[:HAS_TIME_COMPLEXITY]->(:Complexity {notation: $time})")
            params["time"] = time_complexity

        if space_complexity:
            conditions.append("(s)-[:HAS_SPACE_COMPLEXITY]->(:Complexity {notation: $space})")
            params["space"] = space_complexity

        query = f"""
        MATCH (s:Snippet)
        WHERE {" AND ".join(conditions)}
        MATCH (s)-[:HAS_TIME_COMPLEXITY]->(tc:Complexity)
        MATCH (s)-[:HAS_SPACE_COMPLEXITY]->(sc:Complexity)
        OPTIONAL MATCH (s)-[:WRITTEN_IN]->(l:Language)
        RETURN s.id AS id,
               s.title AS title,
               s.description AS description,
               tc.notation AS time_complexity,
               sc.notation AS space_complexity,
               l.name AS language
        ORDER BY s.updated_at DESC
        LIMIT $limit
        """

        return self.execute_query(query, params)


# Singleton service instance
_service: Neo4jService | None = None


def get_neo4j_service() -> Neo4jService:
    """Get or create the Neo4j service singleton."""
    global _service
    if _service is None:
        _service = Neo4jService()
    return _service

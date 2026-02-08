"""Direct sync provider for local development.

Performs Neo4j synchronization inline without a queue.
This is simpler for local development but adds latency to API responses.
"""

import logging
from uuid import UUID

from api.schemas.sync import SnippetSyncEvent
from api.services.sync.provider import SyncProvider

logger = logging.getLogger(__name__)


class DirectSyncProvider(SyncProvider):
    """Sync provider that updates Neo4j directly.

    Uses the same processing logic as the Lambda sync worker,
    but executes it inline instead of via a queue.
    """

    async def sync_analyzed(self, snippet_id: str, user_id: str) -> bool:
        """Sync an analyzed snippet directly to Neo4j."""
        from api.handlers.sync_worker import process_analyzed_event
        from api.services.embedding_service import EmbeddingService
        from api.services.neo4j_service import Neo4jService, get_neo4j_driver
        from common.config import settings

        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
        )

        try:
            driver = get_neo4j_driver()
            if not driver:
                logger.warning(
                    "Neo4j not configured, skipping direct sync",
                    extra={"snippet_id": snippet_id},
                )
                return False

            neo4j_service = Neo4jService(driver)
            embedding_service = EmbeddingService(model=settings.gemini_embedding_model)

            result = process_analyzed_event(event, neo4j_service, embedding_service)

            if result:
                logger.info(
                    "Direct sync completed",
                    extra={"snippet_id": snippet_id, "event_type": "analyzed"},
                )
            return result

        except Exception as e:
            logger.error(
                "Direct sync failed",
                extra={"snippet_id": snippet_id, "error": str(e)},
            )
            return False

    async def sync_deleted(self, snippet_id: str, user_id: str) -> bool:
        """Delete a snippet directly from Neo4j."""
        from api.handlers.sync_worker import process_deleted_event
        from api.services.neo4j_service import Neo4jService, get_neo4j_driver

        event = SnippetSyncEvent.deleted(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
        )

        try:
            driver = get_neo4j_driver()
            if not driver:
                logger.warning(
                    "Neo4j not configured, skipping direct sync",
                    extra={"snippet_id": snippet_id},
                )
                return False

            neo4j_service = Neo4jService(driver)
            result = process_deleted_event(event, neo4j_service)

            if result:
                logger.info(
                    "Direct sync completed",
                    extra={"snippet_id": snippet_id, "event_type": "deleted"},
                )
            return result

        except Exception as e:
            logger.error(
                "Direct sync failed",
                extra={"snippet_id": snippet_id, "error": str(e)},
            )
            return False

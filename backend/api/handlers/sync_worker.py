"""Sync worker Lambda handler for Neo4j synchronization.

This handler processes SQS messages from the snippet-sync queue,
generates embeddings, and syncs snippets to Neo4j.

Uses fully synchronous operations to avoid Lambda event loop issues.
"""

import json
import logging
from typing import Any

from sqlalchemy import select

from api.models.snippet import Snippet
from api.models.user import User
from api.schemas.sync import SnippetSyncEvent
from api.services.database import get_sync_session_factory
from api.services.embedding_service import EmbeddingService
from api.services.neo4j_service import Neo4jService, get_neo4j_driver

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def process_analyzed_event(
    event: SnippetSyncEvent,
    neo4j_service: Neo4jService,
    embedding_service: EmbeddingService,
) -> bool:
    """Process a snippet.analyzed event.

    Fetches snippet from PostgreSQL, generates embedding, and upserts to Neo4j.

    Args:
        event: The sync event.
        neo4j_service: Neo4j service instance.
        embedding_service: Embedding service instance.

    Returns:
        True if successful, False otherwise.
    """
    factory = get_sync_session_factory()
    with factory() as session:
        # Fetch snippet with user info
        result = session.execute(
            select(Snippet, User)
            .join(User, Snippet.user_id == User.id)
            .where(Snippet.id == event.snippet_id)
        )
        row = result.first()

        if not row:
            logger.warning(
                "Snippet not found for sync",
                extra={"snippet_id": str(event.snippet_id)},
            )
            return False

        snippet, user = row

        # Build embedding input from snippet
        embedding_input = embedding_service.build_snippet_embedding_input(
            title=snippet.title,
            description=snippet.description,
            time_complexity=snippet.time_complexity,
            space_complexity=snippet.space_complexity,
            code=snippet.code,
        )

        # Generate embedding (sync)
        embedding = embedding_service.generate_embedding_sync(embedding_input)
        if not embedding:
            logger.error(
                "Failed to generate embedding",
                extra={"snippet_id": str(event.snippet_id)},
            )
            return False

        # Upsert to Neo4j
        neo4j_service.upsert_snippet(
            snippet_id=str(snippet.id),
            user_id=str(user.id),
            title=snippet.title,
            code=snippet.code,
            language=snippet.language,
            time_complexity=snippet.time_complexity or "O(?)",
            space_complexity=snippet.space_complexity or "O(?)",
            embedding=embedding,
            description=snippet.description,
        )

        logger.info(
            "Synced snippet to Neo4j",
            extra={"snippet_id": str(event.snippet_id)},
        )
        return True


def process_deleted_event(
    event: SnippetSyncEvent,
    neo4j_service: Neo4jService,
) -> bool:
    """Process a snippet.deleted event.

    Removes snippet from Neo4j.

    Args:
        event: The sync event.
        neo4j_service: Neo4j service instance.

    Returns:
        True if successful, False otherwise.
    """
    neo4j_service.delete_snippet(str(event.snippet_id))
    logger.info(
        "Deleted snippet from Neo4j",
        extra={"snippet_id": str(event.snippet_id)},
    )
    return True


def process_event(
    event: SnippetSyncEvent,
    neo4j_service: Neo4jService,
    embedding_service: EmbeddingService,
) -> bool:
    """Process a single sync event.

    Args:
        event: The sync event to process.
        neo4j_service: Neo4j service instance.
        embedding_service: Embedding service instance.

    Returns:
        True if successful, False otherwise.
    """
    if event.event_type == "snippet.analyzed":
        return process_analyzed_event(event, neo4j_service, embedding_service)
    elif event.event_type == "snippet.deleted":
        return process_deleted_event(event, neo4j_service)
    else:
        logger.warning(
            "Unknown event type",
            extra={"event_type": event.event_type},
        )
        return False


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for SQS sync events.

    Processes batch of SQS messages, each containing a SnippetSyncEvent.
    Uses fully synchronous processing to avoid Lambda event loop issues.

    Args:
        event: Lambda event with SQS records.
        context: Lambda context.

    Returns:
        Batch item failures for partial batch retry.
    """
    # Use singleton driver for high-throughput - survives Lambda container reuse.
    # NEVER close this driver; for one-off operations use neo4j_driver_context().
    driver = get_neo4j_driver()
    neo4j_service = Neo4jService(driver)
    embedding_service = EmbeddingService()

    records = event.get("Records", [])
    batch_item_failures = []

    for record in records:
        message_id = record.get("messageId", "unknown")
        try:
            body = json.loads(record.get("body", "{}"))
            sync_event = SnippetSyncEvent.model_validate(body)

            success = process_event(sync_event, neo4j_service, embedding_service)

            if not success:
                batch_item_failures.append({"itemIdentifier": message_id})

        except Exception as e:
            logger.error(
                "Failed to process sync event",
                extra={
                    "message_id": message_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}

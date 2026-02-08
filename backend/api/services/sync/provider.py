"""Abstract sync provider interface and factory."""

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Literal

from common.config import settings

logger = logging.getLogger(__name__)

# Valid provider types
SyncProviderType = Literal["sqs", "direct"]


class SyncProvider(ABC):
    """Abstract interface for Neo4j synchronization.

    Implementations handle syncing snippet data from PostgreSQL to Neo4j
    either via a queue (SQS) or directly (for local development).
    """

    @abstractmethod
    async def sync_analyzed(self, snippet_id: str, user_id: str) -> bool:
        """Sync a snippet that has been analyzed.

        Generates embeddings and upserts the snippet to Neo4j.

        Args:
            snippet_id: UUID of the snippet as string.
            user_id: UUID of the owner as string.

        Returns:
            True if sync was successful or enqueued, False on failure.
        """
        ...

    @abstractmethod
    async def sync_deleted(self, snippet_id: str, user_id: str) -> bool:
        """Sync a snippet deletion.

        Removes the snippet from Neo4j.

        Args:
            snippet_id: UUID of the snippet as string.
            user_id: UUID of the owner as string.

        Returns:
            True if sync was successful or enqueued, False on failure.
        """
        ...


@lru_cache
def get_sync_provider() -> SyncProvider | None:
    """Get the configured sync provider instance.

    The provider is determined by the SYNC_PROVIDER setting:
    - "sqs": Use SQS FIFO queue (requires SNIPPET_SYNC_QUEUE_URL)
    - "direct": Sync directly to Neo4j (for local development)
    - Empty/unset: No sync (semantic search won't be updated)

    Returns:
        SyncProvider instance or None if not configured.

    Raises:
        ValueError: If an invalid provider is specified.
        RuntimeError: If provider requirements are not met.
    """
    provider_type = settings.sync_provider

    if not provider_type:
        logger.debug("Sync provider not configured (SYNC_PROVIDER not set)")
        return None

    match provider_type:
        case "sqs":
            from api.services.sync.sqs import SQSSyncProvider

            queue_url = settings.snippet_sync_queue_url
            if not queue_url:
                raise RuntimeError("SYNC_PROVIDER=sqs requires SNIPPET_SYNC_QUEUE_URL to be set")
            logger.info("Using SQS sync provider", extra={"queue_url": queue_url})
            return SQSSyncProvider(queue_url=queue_url)

        case "direct":
            from api.services.sync.direct import DirectSyncProvider

            logger.info("Using direct sync provider (Neo4j sync inline)")
            return DirectSyncProvider()

        case _:
            raise ValueError(
                f"Invalid SYNC_PROVIDER: '{provider_type}'. Valid options: 'sqs', 'direct'"
            )

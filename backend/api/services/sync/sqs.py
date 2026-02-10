"""SQS-based sync provider for production use.

Enqueues sync events to an SQS FIFO queue, which are processed
asynchronously by the sync worker Lambda.
"""

import logging
from functools import lru_cache
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from api.schemas.sync import SnippetSyncEvent
from api.services.sync.provider import SyncProvider
from common.config import settings

if TYPE_CHECKING:
    from mypy_boto3_sqs import SQSClient

logger = logging.getLogger(__name__)


@lru_cache
def _get_sqs_client() -> "SQSClient":
    """Get cached SQS client."""
    return boto3.client("sqs")


class SQSSyncProvider(SyncProvider):
    """Sync provider that enqueues events to SQS.

    Events are processed asynchronously by the sync worker Lambda,
    which handles embedding generation and Neo4j updates.
    """

    def __init__(self, *, queue_url: str | None = None, sqs_client: "SQSClient | None" = None):
        """Initialize SQS sync provider.

        Args:
            queue_url: URL of the SQS FIFO queue. Falls back to
                ``settings.snippet_sync_queue_url`` when not provided.
            sqs_client: Optional SQS client (for testing). Uses default if not provided.

        Raises:
            RuntimeError: If no queue URL is available.
        """
        self._queue_url = queue_url or settings.snippet_sync_queue_url
        if not self._queue_url:
            raise RuntimeError("SQSSyncProvider requires SNIPPET_SYNC_QUEUE_URL to be set")
        self._sqs = sqs_client or _get_sqs_client()

    async def _enqueue_event(self, event: SnippetSyncEvent) -> bool:
        """Enqueue a sync event to SQS.

        Args:
            event: The sync event to enqueue.

        Returns:
            True if successful, False on failure.
        """
        try:
            message = event.to_sqs_message()
            response = self._sqs.send_message(
                QueueUrl=self._queue_url,
                MessageBody=message["MessageBody"],
                MessageGroupId=message["MessageGroupId"],
            )
            message_id = response.get("MessageId")
            logger.info(
                "Enqueued sync event",
                extra={
                    "event_type": event.event_type,
                    "snippet_id": str(event.snippet_id),
                    "message_id": message_id,
                },
            )
            return True
        except ClientError as e:
            logger.error(
                "Failed to enqueue sync event",
                extra={
                    "event_type": event.event_type,
                    "snippet_id": str(event.snippet_id),
                    "error": str(e),
                },
            )
            return False

    async def sync_analyzed(
        self,
        snippet_id: str,
        user_id: str,
        time_complexity: str | None = None,
        space_complexity: str | None = None,
    ) -> bool:
        """Enqueue an analyzed event to SQS."""
        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
            time_complexity=time_complexity,
            space_complexity=space_complexity,
        )
        return await self._enqueue_event(event)

    async def sync_deleted(self, snippet_id: str, user_id: str) -> bool:
        """Enqueue a deleted event to SQS."""
        event = SnippetSyncEvent.deleted(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
        )
        return await self._enqueue_event(event)

"""Sync service for enqueueing Neo4j synchronization events."""

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from api.schemas.sync import SnippetSyncEvent
from common.config import settings

if TYPE_CHECKING:
    from mypy_boto3_sqs import SQSClient

logger = logging.getLogger(__name__)


class SyncService:
    """Service for managing Neo4j sync events via SQS."""

    def __init__(self, sqs_client: "SQSClient", queue_url: str):
        """Initialize sync service.

        Args:
            sqs_client: Boto3 SQS client.
            queue_url: URL of the SQS FIFO queue.
        """
        self._sqs = sqs_client
        self._queue_url = queue_url

    async def enqueue_event(self, event: SnippetSyncEvent) -> str | None:
        """Enqueue a sync event to SQS.

        Args:
            event: The sync event to enqueue.

        Returns:
            Message ID if successful, None if failed.
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
            return message_id
        except ClientError as e:
            logger.error(
                "Failed to enqueue sync event",
                extra={
                    "event_type": event.event_type,
                    "snippet_id": str(event.snippet_id),
                    "error": str(e),
                },
            )
            return None

    async def enqueue_analyzed(self, snippet_id: str, user_id: str) -> str | None:
        """Convenience method to enqueue an analyzed event.

        Args:
            snippet_id: UUID of the snippet as string.
            user_id: UUID of the owner as string.

        Returns:
            Message ID if successful, None if failed.
        """
        from uuid import UUID

        event = SnippetSyncEvent.analyzed(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
        )
        return await self.enqueue_event(event)

    async def enqueue_deleted(self, snippet_id: str, user_id: str) -> str | None:
        """Convenience method to enqueue a deleted event.

        Args:
            snippet_id: UUID of the snippet as string.
            user_id: UUID of the owner as string.

        Returns:
            Message ID if successful, None if failed.
        """
        from uuid import UUID

        event = SnippetSyncEvent.deleted(
            snippet_id=UUID(snippet_id),
            user_id=UUID(user_id),
        )
        return await self.enqueue_event(event)


@lru_cache
def get_sqs_client() -> "SQSClient":
    """Get cached SQS client.

    Returns:
        Boto3 SQS client.
    """
    return boto3.client("sqs")


def get_sync_service() -> SyncService | None:
    """Get sync service instance if configured.

    Returns:
        SyncService configured with settings, or None if not configured.
    """
    queue_url = settings.snippet_sync_queue_url
    if not queue_url:
        logger.debug("Sync service not configured: SNIPPET_SYNC_QUEUE_URL not set")
        return None

    try:
        return SyncService(
            sqs_client=get_sqs_client(),
            queue_url=queue_url,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize sync service: {e}")
        return None

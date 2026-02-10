"""Abstract sync provider interface and factory.

The concrete implementation is selected at runtime via the ``SYNC_PROVIDER``
setting, which must be the fully-qualified Python class name of a
:class:`SyncProvider` subclass (e.g.
``api.services.sync.sqs.SQSSyncProvider``).

This keeps the factory completely generic — no hard-coded ``match/case``
and no magic string keys — while the IaC configs and ``.env`` files specify
exactly which class to load.
"""

import importlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

from common.config import settings

logger = logging.getLogger(__name__)


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


def _load_provider_class(class_path: str) -> type[SyncProvider]:
    """Dynamically import a SyncProvider subclass by its fully-qualified name.

    Args:
        class_path: e.g. ``"api.services.sync.sqs.SQSSyncProvider"``

    Returns:
        The provider **class** (not an instance).

    Raises:
        ValueError: If the path is malformed, the module cannot be imported,
            the attribute doesn't exist, or it isn't a SyncProvider subclass.
    """
    if "." not in class_path:
        raise ValueError(
            f"SYNC_PROVIDER must be a fully-qualified class name "
            f"(e.g. 'api.services.sync.sqs.SQSSyncProvider'), got: '{class_path}'"
        )

    module_path, class_name = class_path.rsplit(".", 1)

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"Cannot import module '{module_path}' from SYNC_PROVIDER='{class_path}': {exc}"
        ) from exc

    cls = getattr(module, class_name, None)
    if cls is None:
        raise ValueError(
            f"Module '{module_path}' has no attribute '{class_name}' (SYNC_PROVIDER='{class_path}')"
        )

    if not (isinstance(cls, type) and issubclass(cls, SyncProvider)):
        raise ValueError(
            f"'{class_path}' is not a SyncProvider subclass (got {type(cls).__name__})"
        )

    return cls


@lru_cache
def get_sync_provider() -> SyncProvider | None:
    """Get the configured sync provider instance.

    The provider is determined by the ``SYNC_PROVIDER`` setting, which must
    be the fully-qualified Python class name of a :class:`SyncProvider`
    subclass.  Examples::

        SYNC_PROVIDER=api.services.sync.sqs.SQSSyncProvider
        SYNC_PROVIDER=api.services.sync.direct.DirectSyncProvider

    The class is instantiated with no arguments — each concrete provider
    reads whatever additional config it needs (queue URL, Neo4j driver,
    etc.) from ``settings`` in its own ``__init__``.

    Returns:
        SyncProvider instance, or ``None`` if ``SYNC_PROVIDER`` is empty.

    Raises:
        ValueError: If the class cannot be loaded or isn't a SyncProvider.
        RuntimeError: If provider-specific requirements are not met.
    """
    class_path = settings.sync_provider

    if not class_path:
        logger.debug("Sync provider not configured (SYNC_PROVIDER not set)")
        return None

    cls = _load_provider_class(class_path)
    logger.info("Loading sync provider: %s", class_path)
    return cls()

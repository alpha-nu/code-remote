"""Sync provider module for Neo4j synchronization.

This module provides an abstraction for syncing snippets to Neo4j.
The concrete implementation is determined by the SYNC_PROVIDER setting.
"""

from api.services.sync.provider import SyncProvider, get_sync_provider

__all__ = [
    "SyncProvider",
    "get_sync_provider",
]

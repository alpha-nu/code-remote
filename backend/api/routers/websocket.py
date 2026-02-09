"""WebSocket endpoint and connection management.

Provides:
- A simple WebSocket server for local development (in-memory connections)
- boto3 API Gateway Management API for production (Lambda → API Gateway WS)

In production (WEBSOCKET_ENDPOINT set), push_to_connection uses the shared
``common.websocket`` module to post through the API Gateway Management API.
Locally, it falls back to the in-memory _connections dict.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from common.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Store active connections (local dev only): connection_id -> WebSocket
_connections: dict[str, WebSocket] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Handles:
    - ping: Returns connection_id (for async execution requests)
    """
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    _connections[connection_id] = websocket

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                # Return connection_id (matches AWS API Gateway behavior)
                await websocket.send_json({"type": "pong", "connection_id": connection_id})

    except WebSocketDisconnect:
        _connections.pop(connection_id, None)
    except Exception:
        _connections.pop(connection_id, None)


async def push_to_connection(connection_id: str, message: dict) -> bool:
    """Push a message to a specific WebSocket connection.

    In production (WEBSOCKET_ENDPOINT configured), uses the shared
    ``common.websocket`` module to post via API Gateway Management API.
    Locally, sends directly through the in-memory WebSocket dict.

    Args:
        connection_id: The connection ID to send to
        message: The message payload to send

    Returns:
        True if message was sent, False if connection not found or gone
    """
    # --- Production path: use API Gateway Management API ---
    if settings.websocket_endpoint:
        return await _push_via_apigw(connection_id, message)

    # --- Local dev path: in-memory WebSocket ---
    ws = _connections.get(connection_id)
    if ws:
        try:
            await ws.send_json(message)
            return True
        except Exception:
            _connections.pop(connection_id, None)
    return False


async def _push_via_apigw(connection_id: str, message: dict) -> bool:
    """Send a message through AWS API Gateway WebSocket Management API."""
    from common.websocket import get_apigw_management_client
    from common.websocket import post_to_connection as _post

    try:
        client = get_apigw_management_client(settings.websocket_endpoint)

        # boto3 is synchronous — run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _post(client, connection_id, message),
        )
    except Exception as e:
        logger.error(f"Failed to push to connection {connection_id}: {e}")
        return False


def get_connection(connection_id: str) -> WebSocket | None:
    """Get a WebSocket connection by ID (local dev only)."""
    return _connections.get(connection_id)

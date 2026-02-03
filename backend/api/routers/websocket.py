"""WebSocket endpoint for local development.

Provides a simple WebSocket server that mimics the AWS API Gateway WebSocket
behavior for local development. Does not use SQS - executes synchronously.
"""

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# Store active connections: connection_id -> WebSocket
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

    Args:
        connection_id: The connection ID to send to
        message: The message payload to send

    Returns:
        True if message was sent, False if connection not found
    """
    ws = _connections.get(connection_id)
    if ws:
        try:
            await ws.send_json(message)
            return True
        except Exception:
            _connections.pop(connection_id, None)
    return False


def get_connection(connection_id: str) -> WebSocket | None:
    """Get a WebSocket connection by ID."""
    return _connections.get(connection_id)

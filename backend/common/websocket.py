"""WebSocket message delivery via AWS API Gateway Management API.

Provides a single, shared interface for pushing messages to WebSocket
connections through the API Gateway Management API.  Used by both:

- **API Lambda** (streaming analysis results from ``analysis.py``)
- **Worker Lambda** (execution results from ``worker.py``)

Local development bypasses this module entirely — the FastAPI WebSocket
router in ``api/routers/websocket.py`` uses an in-memory dict instead.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Cached client — reused across calls within a single Lambda container
_apigw_client = None
_apigw_endpoint: str | None = None


def get_apigw_management_client(endpoint: str):
    """Get (or create) a cached API Gateway Management API client.

    Args:
        endpoint: WebSocket API endpoint (``wss://…`` or ``https://…``).

    Returns:
        Boto3 ``apigatewaymanagementapi`` client.
    """
    global _apigw_client, _apigw_endpoint  # noqa: PLW0603

    # Re-use the existing client when the endpoint hasn't changed
    if _apigw_client is not None and _apigw_endpoint == endpoint:
        return _apigw_client

    import boto3

    from common.config import settings

    https_endpoint = endpoint.replace("wss://", "https://")
    _apigw_client = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=https_endpoint,
        region_name=settings.aws_region,
    )
    _apigw_endpoint = endpoint
    return _apigw_client


def post_to_connection(client, connection_id: str, data: dict) -> bool:
    """Send JSON data to a WebSocket connection.

    Args:
        client: API Gateway Management API client (from
            :func:`get_apigw_management_client`).
        connection_id: Target WebSocket connection ID.
        data: Payload to send (will be JSON-serialised).

    Returns:
        ``True`` if the message was delivered.
        ``False`` if the connection is gone (``GoneException`` / 410).

    Raises:
        ClientError: For any unexpected API Gateway error — the caller
            decides whether to retry (worker) or swallow (analysis).
    """
    from botocore.exceptions import ClientError

    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("GoneException", "410"):
            logger.warning(f"Connection {connection_id} is gone")
            return False
        logger.error(f"Failed to send to connection {connection_id}: {e}")
        raise

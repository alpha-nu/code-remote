"""Worker Lambda handler for async code execution.

This handler processes SQS messages containing code execution jobs,
executes the code in a sandbox, and pushes results via WebSocket.
"""

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from common.config import settings
from executor.runner import execute_code

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_api_gateway_management_client(endpoint: str):
    """Create API Gateway Management API client for WebSocket communication.

    Args:
        endpoint: The WebSocket API endpoint (e.g., https://xxx.execute-api.region.amazonaws.com/prod)

    Returns:
        Boto3 client for API Gateway Management API.
    """
    # Convert wss:// to https:// for management API
    https_endpoint = endpoint.replace("wss://", "https://")
    return boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=https_endpoint,
        region_name=settings.aws_region,
    )


def send_to_connection(client, connection_id: str, data: dict) -> bool:
    """Send data to a WebSocket connection.

    Args:
        client: API Gateway Management API client.
        connection_id: Target WebSocket connection ID.
        data: Data to send (will be JSON serialized).

    Returns:
        True if message was sent, False if connection is gone.
    """
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
        logger.error(f"Failed to send to {connection_id}: {e}")
        raise


def process_execution_job(job: dict) -> dict:
    """Execute code and return result.

    Args:
        job: Job dictionary with code, timeout_seconds, etc.

    Returns:
        Execution result dictionary.
    """
    try:
        result = execute_code(
            code=job["code"],
            timeout_seconds=job.get("timeout_seconds", 30.0),
        )
        return {
            "type": "execution_result",
            "job_id": job["job_id"],
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.error,
            "error_type": result.error_type,
            "execution_time_ms": result.execution_time_ms,
            "timed_out": result.timed_out,
            "security_violations": result.security_violations,
        }
    except Exception as e:
        logger.exception(f"Execution failed for job {job.get('job_id')}")
        return {
            "type": "execution_result",
            "job_id": job.get("job_id"),
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": f"Internal execution error: {e!s}",
            "error_type": type(e).__name__,
            "execution_time_ms": 0.0,
            "timed_out": False,
            "security_violations": [],
        }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for SQS-triggered code execution.

    Processes execution jobs from SQS and sends results via WebSocket.

    Args:
        event: SQS event with Records array.
        context: Lambda context (unused).

    Returns:
        Response with batch item failures (for partial batch retry).
    """
    logger.info(f"Received event with {len(event.get('Records', []))} records")

    websocket_endpoint = settings.websocket_endpoint
    if not websocket_endpoint:
        logger.error("WEBSOCKET_ENDPOINT not configured")
        # Fail all records so they go to DLQ
        return {
            "batchItemFailures": [
                {"itemIdentifier": record["messageId"]} for record in event.get("Records", [])
            ]
        }

    api_client = get_api_gateway_management_client(websocket_endpoint)
    batch_failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]

        try:
            # Parse job from SQS message
            job = json.loads(record["body"])
            connection_id = job.get("connection_id")
            job_id = job.get("job_id")

            logger.info(f"Processing job {job_id} for connection {connection_id}")

            if not connection_id:
                logger.error(f"No connection_id in job {job_id}")
                continue  # Don't retry - invalid message

            # Execute the code
            result = process_execution_job(job)

            # Send result to WebSocket connection
            sent = send_to_connection(api_client, connection_id, result)
            if not sent:
                # Connection is gone - no point in retrying
                logger.warning(f"Skipping job {job_id} - connection gone")
                continue

            logger.info(f"Completed job {job_id}, success={result['success']}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {e}")
            # Don't retry - message is malformed
            continue
        except Exception:
            logger.exception(f"Failed to process message {message_id}")
            # Report failure for retry
            batch_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_failures}

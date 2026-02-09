"""Worker Lambda handler for async code execution.

This handler processes SQS messages containing code execution jobs,
executes the code in a sandbox, and pushes results via WebSocket.
"""

import json
import logging
from typing import Any

from common.config import settings
from common.websocket import get_apigw_management_client, post_to_connection
from executor.runner import execute_code

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

    api_client = get_apigw_management_client(websocket_endpoint)
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
            sent = post_to_connection(api_client, connection_id, result)
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

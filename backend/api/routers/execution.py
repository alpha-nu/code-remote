"""Code execution endpoint."""

import json
import uuid

import boto3
from fastapi import APIRouter, Depends, HTTPException

from api.auth import User, get_current_user
from api.schemas.execution import (
    AsyncExecutionRequest,
    ExecutionRequest,
    ExecutionResponse,
    JobSubmittedResponse,
)
from api.services.executor_service import ExecutorService, get_executor_service
from common.config import settings

router = APIRouter()


def get_sqs_client():
    """Get SQS client for sending messages to queue."""
    return boto3.client("sqs", region_name=settings.aws_region)


@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(
    request: ExecutionRequest,
    user: User = Depends(get_current_user),
    executor: ExecutorService = Depends(get_executor_service),
) -> ExecutionResponse:
    """Execute Python code synchronously in a sandboxed environment.

    Requires authentication. The code is validated for security
    (blocked imports, dangerous functions) and executed with
    resource limits (timeout, memory).

    Args:
        request: The execution request containing code and optional timeout.
        user: The authenticated user (injected from JWT token).
        executor: The executor service (injected).

    Returns:
        ExecutionResponse with stdout, stderr, errors, and execution metadata.

    Security:
        - Only whitelisted imports allowed (math, json, collections, etc.)
        - Dangerous built-ins blocked (eval, exec, open, etc.)
        - Execution timeout enforced (max 30 seconds)
        - Code size limited to 10KB
    """
    return await executor.execute(
        code=request.code,
        timeout_seconds=request.timeout_seconds,
    )


@router.post("/execute/async", response_model=JobSubmittedResponse)
async def execute_code_async(
    request: AsyncExecutionRequest,
    user: User = Depends(get_current_user),
) -> JobSubmittedResponse:
    """Submit Python code for asynchronous execution.

    The code is queued for execution and results will be delivered
    via WebSocket to the provided connection_id.

    Args:
        request: The async execution request with code and connection_id.
        user: The authenticated user (injected from JWT token).

    Returns:
        JobSubmittedResponse with job_id and queued status.

    Raises:
        HTTPException: If queueing fails or queue not configured.
    """
    if not settings.execution_queue_url:
        raise HTTPException(
            status_code=503,
            detail="Async execution not available - queue not configured",
        )

    job_id = str(uuid.uuid4())

    # Build message for SQS
    message = {
        "job_id": job_id,
        "user_id": user.id,
        "connection_id": request.connection_id,
        "code": request.code,
        "timeout_seconds": request.timeout_seconds,
    }

    try:
        sqs = get_sqs_client()
        sqs.send_message(
            QueueUrl=settings.execution_queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=user.sub,  # Group by user for ordering
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue execution job: {e!s}",
        ) from e

    return JobSubmittedResponse(job_id=job_id, status="queued")

"""Code execution endpoint."""

import asyncio
import json
import uuid

import boto3
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.auth import User, get_current_user
from api.routers.websocket import push_to_connection
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
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    executor: ExecutorService = Depends(get_executor_service),
) -> JobSubmittedResponse:
    """Submit Python code for asynchronous execution.

    The code is queued for execution and results will be delivered
    via WebSocket to the provided connection_id.

    In production (with SQS), the job is queued and processed by a worker.
    In local development (no SQS), execution happens in a background task.

    Args:
        request: The async execution request with code and connection_id.
        background_tasks: FastAPI background tasks for local execution.
        user: The authenticated user (injected from JWT token).
        executor: The executor service for local execution fallback.

    Returns:
        JobSubmittedResponse with job_id and queued status.

    Raises:
        HTTPException: If queueing fails.
    """
    job_id = str(uuid.uuid4())

    # If SQS is configured (production), use the queue
    if settings.execution_queue_url:
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
    else:
        # Local development: execute in background task and push via WebSocket
        background_tasks.add_task(
            _execute_and_push,
            job_id=job_id,
            connection_id=request.connection_id,
            code=request.code,
            timeout_seconds=request.timeout_seconds,
            executor=executor,
        )

    return JobSubmittedResponse(job_id=job_id, status="queued")


async def _execute_and_push(
    job_id: str,
    connection_id: str,
    code: str,
    timeout_seconds: int,
    executor: ExecutorService,
) -> None:
    """Execute code and push result via WebSocket (local dev only)."""
    # Small delay to ensure the HTTP response is sent first
    await asyncio.sleep(0.1)

    # Execute the code
    result = await executor.execute(code=code, timeout_seconds=timeout_seconds)

    # Push result via WebSocket
    message = {
        "type": "execution_result",
        "job_id": job_id,
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error": result.error,
        "error_type": result.error_type,
        "execution_time_ms": result.execution_time_ms,
        "timed_out": result.timed_out,
        "security_violations": [
            {"line": v.line, "column": v.column, "message": v.message}
            for v in result.security_violations
        ],
    }

    await push_to_connection(connection_id, message)

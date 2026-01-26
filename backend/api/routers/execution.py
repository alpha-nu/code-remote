"""Code execution endpoint."""

from fastapi import APIRouter, Depends

from api.schemas.execution import ExecutionRequest, ExecutionResponse
from api.services.executor_service import ExecutorService, get_executor_service

router = APIRouter()


@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(
    request: ExecutionRequest,
    executor: ExecutorService = Depends(get_executor_service),
) -> ExecutionResponse:
    """Execute Python code in a sandboxed environment.

    The code is validated for security (blocked imports, dangerous functions)
    and executed with resource limits (timeout, memory).

    Args:
        request: The execution request containing code and optional timeout.
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

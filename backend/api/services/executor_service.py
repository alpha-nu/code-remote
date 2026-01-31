"""Execution service for running user code."""

import os

from api.schemas.execution import ExecutionResponse, SecurityViolationResponse
from common.config import settings


def is_lambda_environment() -> bool:
    """Check if we're running in AWS Lambda."""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


class ExecutorService:
    """Service for executing user-submitted Python code."""

    def __init__(self, timeout_seconds: float | None = None):
        """Initialize the executor service.

        Args:
            timeout_seconds: Maximum execution time. Defaults to config value.
        """
        self.default_timeout = timeout_seconds or settings.execution_timeout_seconds

    async def execute(
        self,
        code: str,
        timeout_seconds: float | None = None,
    ) -> ExecutionResponse:
        """Execute Python code in a sandboxed environment.

        In Lambda, uses in-process execution with restricted globals.
        Locally, uses subprocess-based execution.

        Args:
            code: The Python source code to execute.
            timeout_seconds: Maximum execution time (overrides default).

        Returns:
            ExecutionResponse with results or error information.
        """
        timeout = timeout_seconds or self.default_timeout

        # Validate code size
        if len(code.encode("utf-8")) > settings.max_code_size_bytes:
            return ExecutionResponse(
                success=False,
                error=f"Code exceeds maximum size of {settings.max_code_size_bytes} bytes",
                error_type="ValidationError",
            )

        # In Lambda, use in-process execution with restricted globals sandbox
        if is_lambda_environment():
            from api.services.lambda_executor import get_lambda_executor

            lambda_executor = get_lambda_executor()
            return lambda_executor.execute(code, timeout_seconds=timeout)

        # Local development: use subprocess-based execution
        from executor import ExecutionResult, execute_code

        result: ExecutionResult = execute_code(code, timeout_seconds=timeout)

        # Convert to response model
        return ExecutionResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            error=result.error,
            error_type=result.error_type,
            execution_time_ms=result.execution_time_ms,
            timed_out=result.timed_out,
            security_violations=[
                SecurityViolationResponse(
                    line=v["line"],
                    column=v["column"],
                    message=v["message"],
                )
                for v in result.security_violations
            ],
        )


# Singleton instance for dependency injection
_executor_service: ExecutorService | None = None


def get_executor_service() -> ExecutorService:
    """Get the executor service instance (dependency injection)."""
    global _executor_service
    if _executor_service is None:
        _executor_service = ExecutorService()
    return _executor_service

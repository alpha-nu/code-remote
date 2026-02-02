"""Main code execution runner with sandboxing.

For local development, uses multiprocessing for stronger isolation.
Security is managed centrally via executor.security module.
"""

import multiprocessing
import sys
import traceback
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from executor.security import create_safe_builtins, is_code_safe


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    error: str | None = None
    error_type: str | None = None
    execution_time_ms: float = 0.0
    timed_out: bool = False
    security_violations: list[dict] = field(default_factory=list)


def _execute_in_sandbox(
    code: str,
    result_queue: multiprocessing.Queue,
    extra_modules: set[str] | None = None,
) -> None:
    """Execute code in a sandboxed environment.

    This function runs in a separate process.
    """
    import time

    stdout_capture = StringIO()
    stderr_capture = StringIO()

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    start_time = time.perf_counter()

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # Create restricted globals using centralized security
        restricted_globals = {
            "__builtins__": create_safe_builtins(extra_modules),
            "__name__": "__main__",
            "__doc__": None,
        }

        # Execute the code
        exec(code, restricted_globals)  # noqa: S102

        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        result_queue.put(
            ExecutionResult(
                success=True,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                execution_time_ms=execution_time_ms,
            )
        )

    except Exception as e:
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        # Get the traceback, filtering out internal frames
        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        # Filter to show only user code errors
        filtered_tb = []
        for line in tb_lines:
            if "<string>" in line or not line.strip().startswith("File"):
                filtered_tb.append(line)

        result_queue.put(
            ExecutionResult(
                success=False,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=execution_time_ms,
            )
        )

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def execute_code(
    code: str,
    timeout_seconds: float = 30.0,
    extra_modules: set[str] | None = None,
) -> ExecutionResult:
    """Execute Python code in a sandboxed environment.

    Args:
        code: The Python source code to execute.
        timeout_seconds: Maximum execution time in seconds.
        extra_modules: Additional modules to allow beyond the base set.

    Returns:
        ExecutionResult with stdout, stderr, and execution info.
    """
    # First, validate the code for security
    is_safe, violations = is_code_safe(code, extra_modules)

    if not is_safe:
        return ExecutionResult(
            success=False,
            error="Security validation failed",
            error_type="SecurityError",
            security_violations=[
                {
                    "line": v.line,
                    "column": v.column,
                    "message": v.message,
                }
                for v in violations
            ],
        )

    # Create a queue to receive the result
    result_queue: multiprocessing.Queue = multiprocessing.Queue()

    # Create and start the process
    process = multiprocessing.Process(
        target=_execute_in_sandbox,
        args=(code, result_queue, extra_modules),
    )
    process.start()

    # Wait for the process to complete or timeout
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        # Timeout occurred - terminate the process
        process.terminate()
        process.join(timeout=1.0)

        # If still alive, force kill
        if process.is_alive():
            process.kill()
            process.join()

        return ExecutionResult(
            success=False,
            error=f"Execution timed out after {timeout_seconds} seconds",
            error_type="TimeoutError",
            timed_out=True,
        )

    # Get the result from the queue
    try:
        result = result_queue.get_nowait()
        return result
    except Exception:
        return ExecutionResult(
            success=False,
            error="Failed to retrieve execution result",
            error_type="InternalError",
        )

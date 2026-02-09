"""Main code execution runner with sandboxing.

Executes user code in-process with restricted builtins.
Security is managed centrally via executor.security module.
"""

import sys
import time
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


def execute_code(
    code: str,
    timeout_seconds: float = 30.0,
    extra_modules: set[str] | None = None,
) -> ExecutionResult:
    """Execute Python code in a sandboxed environment.

    Args:
        code: The Python source code to execute.
        timeout_seconds: Maximum execution time in seconds (for reference only,
            actual timeout enforcement is handled by the caller/Lambda).
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

    # Capture stdout/stderr
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

        return ExecutionResult(
            success=True,
            stdout=stdout_capture.getvalue(),
            stderr=stderr_capture.getvalue(),
            execution_time_ms=execution_time_ms,
        )

    except Exception as e:
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        return ExecutionResult(
            success=False,
            stdout=stdout_capture.getvalue(),
            stderr=stderr_capture.getvalue(),
            error=str(e),
            error_type=type(e).__name__,
            execution_time_ms=execution_time_ms,
        )

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

"""Lambda-compatible code executor using exec() with sandboxing.

This executor runs code directly in the Lambda environment using exec()
with a restricted globals environment. This is a fast, in-process
execution model suitable for simple code execution.

Security is managed centrally via executor.security module.
"""

import io
import threading
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from api.schemas.execution import ExecutionResponse
from common.config import settings
from executor.security import create_safe_builtins


class LambdaExecutor:
    """Execute Python code safely within Lambda environment."""

    def __init__(self, timeout_seconds: float | None = None):
        """Initialize the executor.

        Args:
            timeout_seconds: Maximum execution time. Defaults to config value.
        """
        self.default_timeout = timeout_seconds or settings.execution_timeout_seconds
        # Get extra allowed modules from config
        self.extra_modules = settings.extra_allowed_imports_set

    def execute(
        self,
        code: str,
        timeout_seconds: float | None = None,
    ) -> ExecutionResponse:
        """Execute Python code with captured output.

        Args:
            code: Python source code to execute.
            timeout_seconds: Maximum execution time.

        Returns:
            ExecutionResponse with results.
        """
        timeout = timeout_seconds or self.default_timeout
        start_time = time.time()

        # Validate code size
        if len(code.encode("utf-8")) > settings.max_code_size_bytes:
            return ExecutionResponse(
                success=False,
                error=f"Code exceeds maximum size of {settings.max_code_size_bytes} bytes",
                error_type="ValidationError",
            )

        # Capture stdout/stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Result container for thread
        result: dict[str, Any] = {
            "success": False,
            "error": None,
            "error_type": None,
            "completed": False,
        }

        # Create safe builtins with any extra allowed modules from config
        safe_builtins = create_safe_builtins(self.extra_modules or None)

        def run_code():
            """Run code in a restricted environment."""
            try:
                # Create restricted globals
                restricted_globals = {
                    "__builtins__": safe_builtins,
                    "__name__": "__main__",
                    "__doc__": None,
                }

                # Redirect stdout/stderr and execute
                # Use same dict for globals and locals so defined functions can call themselves (recursion)
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(compile(code, "<user_code>", "exec"), restricted_globals)

                result["success"] = True
                result["completed"] = True

            except SyntaxError as e:
                result["error"] = f"Line {e.lineno}: {e.msg}"
                result["error_type"] = "SyntaxError"
                result["completed"] = True

            except ImportError as e:
                result["error"] = str(e)
                result["error_type"] = "SecurityError"
                result["completed"] = True

            except Exception as e:
                # Capture the traceback but sanitize it
                tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                # Filter out internal frames
                user_tb = [
                    line
                    for line in tb_lines
                    if "<user_code>" in line or not line.startswith("  File")
                ]
                result["error"] = f"{type(e).__name__}: {e}"
                result["error_type"] = type(e).__name__
                # Add traceback to stderr
                stderr_capture.write("".join(user_tb))
                result["completed"] = True

        # Run in thread with timeout
        thread = threading.Thread(target=run_code, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        execution_time_ms = int((time.time() - start_time) * 1000)

        if not result["completed"]:
            # Thread didn't complete - timeout
            return ExecutionResponse(
                success=False,
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                error=f"Execution timed out after {timeout} seconds",
                error_type="TimeoutError",
                execution_time_ms=execution_time_ms,
                timed_out=True,
            )

        return ExecutionResponse(
            success=result["success"],
            stdout=stdout_capture.getvalue(),
            stderr=stderr_capture.getvalue(),
            error=result["error"],
            error_type=result["error_type"],
            execution_time_ms=execution_time_ms,
            timed_out=False,
        )


# Singleton instance
_lambda_executor: LambdaExecutor | None = None


def get_lambda_executor() -> LambdaExecutor:
    """Get the Lambda executor instance."""
    global _lambda_executor
    if _lambda_executor is None:
        _lambda_executor = LambdaExecutor()
    return _lambda_executor

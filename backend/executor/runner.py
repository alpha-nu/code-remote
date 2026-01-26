"""Main code execution runner with sandboxing."""

import multiprocessing
import sys
import traceback
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from executor.security import ALLOWED_IMPORTS, BLOCKED_BUILTINS, is_code_safe


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


def _create_safe_import():
    """Create a safe import function that only allows whitelisted modules."""

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        """Import function that only allows whitelisted modules."""
        # Get the top-level module name
        module_name = name.split(".")[0]

        if module_name not in ALLOWED_IMPORTS:
            raise ImportError(
                f"Import of '{name}' is not allowed. Allowed modules: {sorted(ALLOWED_IMPORTS)}"
            )

        # Use the real __import__ for allowed modules
        return __builtins__["__import__"](name, globals, locals, fromlist, level)

    return safe_import


def _create_safe_builtins() -> dict:
    """Create a restricted builtins dictionary."""
    import builtins

    safe_builtins = {}
    for name in dir(builtins):
        if name not in BLOCKED_BUILTINS and not name.startswith("_"):
            safe_builtins[name] = getattr(builtins, name)

    # Add the safe import function
    safe_builtins["__import__"] = _create_safe_import()

    # Add essential dunder methods needed for Python features
    safe_builtins["__build_class__"] = builtins.__build_class__  # Required for class definitions
    safe_builtins["__name__"] = "__main__"  # For if __name__ == "__main__" checks

    # Add safe versions of some functions
    safe_builtins["print"] = print
    safe_builtins["range"] = range
    safe_builtins["len"] = len
    safe_builtins["int"] = int
    safe_builtins["float"] = float
    safe_builtins["str"] = str
    safe_builtins["bool"] = bool
    safe_builtins["list"] = list
    safe_builtins["dict"] = dict
    safe_builtins["set"] = set
    safe_builtins["tuple"] = tuple
    safe_builtins["sorted"] = sorted
    safe_builtins["reversed"] = reversed
    safe_builtins["enumerate"] = enumerate
    safe_builtins["zip"] = zip
    safe_builtins["map"] = map
    safe_builtins["filter"] = filter
    safe_builtins["sum"] = sum
    safe_builtins["min"] = min
    safe_builtins["max"] = max
    safe_builtins["abs"] = abs
    safe_builtins["round"] = round
    safe_builtins["pow"] = pow
    safe_builtins["divmod"] = divmod
    safe_builtins["isinstance"] = isinstance
    safe_builtins["issubclass"] = issubclass
    safe_builtins["type"] = type
    safe_builtins["id"] = id
    safe_builtins["hash"] = hash
    safe_builtins["repr"] = repr
    safe_builtins["format"] = format
    safe_builtins["chr"] = chr
    safe_builtins["ord"] = ord
    safe_builtins["bin"] = bin
    safe_builtins["hex"] = hex
    safe_builtins["oct"] = oct
    safe_builtins["any"] = any
    safe_builtins["all"] = all
    safe_builtins["slice"] = slice
    safe_builtins["frozenset"] = frozenset
    safe_builtins["bytes"] = bytes
    safe_builtins["bytearray"] = bytearray
    safe_builtins["object"] = object
    safe_builtins["property"] = property
    safe_builtins["staticmethod"] = staticmethod
    safe_builtins["classmethod"] = classmethod
    safe_builtins["super"] = super

    # Exceptions
    safe_builtins["Exception"] = Exception
    safe_builtins["BaseException"] = BaseException
    safe_builtins["ValueError"] = ValueError
    safe_builtins["TypeError"] = TypeError
    safe_builtins["KeyError"] = KeyError
    safe_builtins["IndexError"] = IndexError
    safe_builtins["AttributeError"] = AttributeError
    safe_builtins["RuntimeError"] = RuntimeError
    safe_builtins["StopIteration"] = StopIteration
    safe_builtins["ZeroDivisionError"] = ZeroDivisionError
    safe_builtins["AssertionError"] = AssertionError
    safe_builtins["NotImplementedError"] = NotImplementedError
    safe_builtins["OverflowError"] = OverflowError
    safe_builtins["RecursionError"] = RecursionError

    # Constants
    safe_builtins["True"] = True
    safe_builtins["False"] = False
    safe_builtins["None"] = None

    return safe_builtins


def _execute_in_sandbox(
    code: str,
    result_queue: multiprocessing.Queue,
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

        # Create restricted globals
        restricted_globals = {
            "__builtins__": _create_safe_builtins(),
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


def execute_code(code: str, timeout_seconds: float = 30.0) -> ExecutionResult:
    """Execute Python code in a sandboxed environment.

    Args:
        code: The Python source code to execute.
        timeout_seconds: Maximum execution time in seconds.

    Returns:
        ExecutionResult with stdout, stderr, and execution info.
    """
    # First, validate the code for security
    is_safe, violations = is_code_safe(code)

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
        args=(code, result_queue),
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

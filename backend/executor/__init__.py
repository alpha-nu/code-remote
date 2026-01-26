"""Sandboxed Python code executor.

This module provides secure execution of untrusted Python code with:
- Import restrictions (whitelist only)
- Blocked dangerous built-in functions
- Timeout enforcement
- Resource limits (when run in container)
"""

from executor.runner import ExecutionResult, execute_code
from executor.security import (
    ALLOWED_IMPORTS,
    BLOCKED_BUILTINS,
    SecurityViolation,
    is_code_safe,
    validate_code,
)

__all__ = [
    "execute_code",
    "ExecutionResult",
    "validate_code",
    "is_code_safe",
    "SecurityViolation",
    "ALLOWED_IMPORTS",
    "BLOCKED_BUILTINS",
]

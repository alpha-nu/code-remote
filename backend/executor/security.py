"""Security module for import restrictions and AST validation."""

import ast
from dataclasses import dataclass

# Whitelist of allowed modules for user code
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        # Safe built-in modules
        "math",
        "cmath",
        "decimal",
        "fractions",
        "random",
        "statistics",
        # Data structures
        "collections",
        "heapq",
        "bisect",
        "array",
        # Functional programming
        "itertools",
        "functools",
        "operator",
        # String and text
        "string",
        "re",
        "textwrap",
        # Data formats
        "json",
        "csv",
        # Date and time
        "datetime",
        "calendar",
        "time",
        # Type hints
        "typing",
        "dataclasses",
        # Other safe modules
        "copy",
        "pprint",
        "enum",
        "abc",
    }
)

# Completely blocked built-in functions
BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "__import__",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "breakpoint",
        "help",
        "memoryview",
    }
)


@dataclass
class SecurityViolation:
    """Represents a security violation in user code."""

    line: int
    column: int
    message: str


class SecurityValidator(ast.NodeVisitor):
    """AST visitor that checks for security violations."""

    def __init__(self) -> None:
        self.violations: list[SecurityViolation] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check regular import statements."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name not in ALLOWED_IMPORTS:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Import of '{alias.name}' is not allowed. "
                        f"Allowed modules: {sorted(ALLOWED_IMPORTS)}",
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from...import statements."""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name not in ALLOWED_IMPORTS:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Import from '{node.module}' is not allowed. "
                        f"Allowed modules: {sorted(ALLOWED_IMPORTS)}",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for blocked function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Use of '{node.func.id}()' is not allowed.",
                    )
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check for dangerous attribute access patterns."""
        # Block access to dunder attributes that could be exploited
        if node.attr.startswith("__") and node.attr.endswith("__"):
            dangerous_attrs = {
                "__class__",
                "__bases__",
                "__subclasses__",
                "__mro__",
                "__globals__",
                "__code__",
                "__builtins__",
                "__import__",
            }
            if node.attr in dangerous_attrs:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Access to '{node.attr}' is not allowed.",
                    )
                )
        self.generic_visit(node)


def validate_code(code: str) -> list[SecurityViolation]:
    """Validate code for security violations.

    Args:
        code: The Python source code to validate.

    Returns:
        List of security violations found, empty if code is safe.

    Raises:
        SyntaxError: If code cannot be parsed.
    """
    tree = ast.parse(code)
    validator = SecurityValidator()
    validator.visit(tree)
    return validator.violations


def is_code_safe(code: str) -> tuple[bool, list[SecurityViolation]]:
    """Check if code passes security validation.

    Args:
        code: The Python source code to check.

    Returns:
        Tuple of (is_safe, violations).
    """
    try:
        violations = validate_code(code)
        return len(violations) == 0, violations
    except SyntaxError as e:
        return False, [
            SecurityViolation(
                line=e.lineno or 1,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
            )
        ]

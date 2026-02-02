"""Security module for import restrictions and AST validation."""

import ast
import builtins
from collections.abc import Callable
from dataclasses import dataclass

# =============================================================================
# ALLOWED IMPORTS - Base set of safe modules for user code
# =============================================================================
BASE_ALLOWED_IMPORTS: frozenset[str] = frozenset(
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

# Legacy alias for backwards compatibility
ALLOWED_IMPORTS = BASE_ALLOWED_IMPORTS


def get_allowed_imports(extra_modules: set[str] | None = None) -> frozenset[str]:
    """Get the set of allowed imports, optionally with extra modules.

    Args:
        extra_modules: Additional modules to allow (e.g., for dev environments).

    Returns:
        Frozenset of allowed module names.
    """
    if extra_modules:
        return BASE_ALLOWED_IMPORTS | frozenset(extra_modules)
    return BASE_ALLOWED_IMPORTS


# =============================================================================
# BLOCKED BUILTINS - Functions that are never allowed
# =============================================================================
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

# =============================================================================
# SAFE BUILTINS - Explicit whitelist of safe built-in functions and types
# =============================================================================
SAFE_BUILTINS: dict = {
    # Constants
    "True": True,
    "False": False,
    "None": None,
    # Type constructors
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    "object": object,
    "complex": complex,
    # Built-in functions (safe subset)
    "abs": abs,
    "all": all,
    "any": any,
    "ascii": ascii,
    "bin": bin,
    "callable": callable,
    "chr": chr,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "format": format,
    "hash": hash,
    "hex": hex,
    "id": id,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "slice": slice,
    "sorted": sorted,
    "sum": sum,
    "zip": zip,
    # Class-related
    "property": property,
    "staticmethod": staticmethod,
    "classmethod": classmethod,
    "super": super,
    "type": type,
    # Exceptions
    "Exception": Exception,
    "BaseException": BaseException,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "ZeroDivisionError": ZeroDivisionError,
    "OverflowError": OverflowError,
    "MemoryError": MemoryError,
    "AssertionError": AssertionError,
    "NotImplementedError": NotImplementedError,
    "RecursionError": RecursionError,
    "ImportError": ImportError,
    "ModuleNotFoundError": ModuleNotFoundError,
    "NameError": NameError,
    "SyntaxError": SyntaxError,
    "IndentationError": IndentationError,
    "TabError": TabError,
    "ArithmeticError": ArithmeticError,
    "FloatingPointError": FloatingPointError,
    "LookupError": LookupError,
    "OSError": OSError,  # Needed for some stdlib modules even if we block file ops
    "EOFError": EOFError,
    "GeneratorExit": GeneratorExit,
    "SystemExit": SystemExit,
    "KeyboardInterrupt": KeyboardInterrupt,
    "StopAsyncIteration": StopAsyncIteration,
    "Warning": Warning,
    "UserWarning": UserWarning,
    "DeprecationWarning": DeprecationWarning,
    "PendingDeprecationWarning": PendingDeprecationWarning,
    "RuntimeWarning": RuntimeWarning,
    "SyntaxWarning": SyntaxWarning,
    "FutureWarning": FutureWarning,
    "UnicodeError": UnicodeError,
    "UnicodeDecodeError": UnicodeDecodeError,
    "UnicodeEncodeError": UnicodeEncodeError,
    "UnicodeTranslateError": UnicodeTranslateError,
}


def create_safe_import(allowed_imports: frozenset[str]) -> Callable:
    """Create a safe import function that only allows whitelisted modules.

    Args:
        allowed_imports: Set of module names that are allowed to be imported.

    Returns:
        A restricted __import__ function.
    """
    # Capture the real import at creation time
    real_import = builtins.__import__

    def safe_import(
        name: str,
        globals_dict: dict | None = None,
        locals_dict: dict | None = None,
        fromlist: tuple = (),
        level: int = 0,
    ):
        """Import function that only allows whitelisted modules."""
        # Get the top-level module name
        module_name = name.split(".")[0]

        if module_name not in allowed_imports:
            raise ImportError(
                f"Import of '{name}' is not allowed. Allowed modules: {sorted(allowed_imports)}"
            )

        return real_import(name, globals_dict, locals_dict, fromlist, level)

    return safe_import


def create_safe_builtins(
    extra_modules: set[str] | None = None,
) -> dict:
    """Create a restricted builtins dictionary for sandboxed execution.

    Args:
        extra_modules: Additional modules to allow for import.

    Returns:
        A dictionary of safe builtins to use as __builtins__ in exec().
    """
    allowed = get_allowed_imports(extra_modules)

    # Start with the explicit safe builtins
    safe_builtins = SAFE_BUILTINS.copy()

    # Add the safe import function
    safe_builtins["__import__"] = create_safe_import(allowed)

    # Add essential dunder methods needed for Python features
    safe_builtins["__build_class__"] = builtins.__build_class__
    safe_builtins["__name__"] = "__main__"

    return safe_builtins


@dataclass
class SecurityViolation:
    """Represents a security violation in user code."""

    line: int
    column: int
    message: str


class SecurityValidator(ast.NodeVisitor):
    """AST visitor that checks for security violations."""

    def __init__(self, allowed_imports: frozenset[str] | None = None) -> None:
        self.violations: list[SecurityViolation] = []
        self.allowed_imports = allowed_imports or BASE_ALLOWED_IMPORTS

    def visit_Import(self, node: ast.Import) -> None:
        """Check regular import statements."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name not in self.allowed_imports:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Import of '{alias.name}' is not allowed. "
                        f"Allowed modules: {sorted(self.allowed_imports)}",
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from...import statements."""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name not in self.allowed_imports:
                self.violations.append(
                    SecurityViolation(
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Import from '{node.module}' is not allowed. "
                        f"Allowed modules: {sorted(self.allowed_imports)}",
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


def validate_code(
    code: str,
    extra_modules: set[str] | None = None,
) -> list[SecurityViolation]:
    """Validate code for security violations.

    Args:
        code: The Python source code to validate.
        extra_modules: Additional modules to allow.

    Returns:
        List of security violations found, empty if code is safe.

    Raises:
        SyntaxError: If code cannot be parsed.
    """
    tree = ast.parse(code)
    allowed = get_allowed_imports(extra_modules)
    validator = SecurityValidator(allowed_imports=allowed)
    validator.visit(tree)
    return validator.violations


def is_code_safe(
    code: str,
    extra_modules: set[str] | None = None,
) -> tuple[bool, list[SecurityViolation]]:
    """Check if code passes security validation.

    Args:
        code: The Python source code to check.
        extra_modules: Additional modules to allow.

    Returns:
        Tuple of (is_safe, violations).
    """
    try:
        violations = validate_code(code, extra_modules)
        return len(violations) == 0, violations
    except SyntaxError as e:
        return False, [
            SecurityViolation(
                line=e.lineno or 1,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
            )
        ]

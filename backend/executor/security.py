"""Security module for import restrictions and AST validation."""

import ast
import builtins
import decimal as _decimal
import functools as _functools
import random as _random
import re as _re
import time as _time
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

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

# Modules that need restricted versions (will be intercepted by safe_import)
RESTRICTED_MODULES: frozenset[str] = frozenset({"time", "random", "functools", "re", "decimal"})

# Legacy alias for backwards compatibility
ALLOWED_IMPORTS = BASE_ALLOWED_IMPORTS

# =============================================================================
# RESOURCE LIMITS - Prevent abuse through excessive resource consumption
# =============================================================================
MAX_RANDOM_BYTES = 1024 * 1024  # 1MB max for randbytes
MAX_RANDOM_SEQUENCE = 100_000  # Max k for choices/sample
MAX_REGEX_INPUT_LENGTH = 100_000  # Max input string for regex operations
MAX_REGEX_PATTERN_LENGTH = 1000  # Max regex pattern length
MAX_DECIMAL_PRECISION = 1000  # Max decimal precision
MAX_LRU_CACHE_SIZE = 1000  # Max LRU cache size (None not allowed)


# =============================================================================
# RESTRICTED MODULES - Safe wrappers that block abusive methods
# =============================================================================


class SecurityError(Exception):
    """Raised when a security restriction is violated."""

    pass


def _create_restricted_time() -> ModuleType:
    """Create a restricted time module without sleep()."""
    restricted = ModuleType("time")

    # Safe timing functions
    restricted.time = _time.time
    restricted.time_ns = _time.time_ns
    restricted.monotonic = _time.monotonic
    restricted.monotonic_ns = _time.monotonic_ns
    restricted.perf_counter = _time.perf_counter
    restricted.perf_counter_ns = _time.perf_counter_ns
    restricted.process_time = _time.process_time
    restricted.process_time_ns = _time.process_time_ns
    restricted.thread_time = _time.thread_time
    restricted.thread_time_ns = _time.thread_time_ns

    # Safe formatting/parsing functions
    restricted.strftime = _time.strftime
    restricted.strptime = _time.strptime
    restricted.gmtime = _time.gmtime
    restricted.localtime = _time.localtime
    restricted.mktime = _time.mktime
    restricted.asctime = _time.asctime
    restricted.ctime = _time.ctime

    # Safe constants
    restricted.timezone = _time.timezone
    restricted.altzone = _time.altzone
    restricted.daylight = _time.daylight
    restricted.tzname = _time.tzname

    # Struct time
    restricted.struct_time = _time.struct_time

    # Block sleep with a clear error
    def blocked_sleep(seconds):
        raise SecurityError(
            "time.sleep() is not allowed - it can exhaust execution time. "
            "Use algorithmic solutions instead of delays."
        )

    restricted.sleep = blocked_sleep

    return restricted


def _create_restricted_random() -> ModuleType:
    """Create a restricted random module with size limits."""
    restricted = ModuleType("random")

    # Copy all safe attributes
    for attr in [
        "Random",
        "seed",
        "getstate",
        "setstate",
        "random",
        "uniform",
        "triangular",
        "randint",
        "randrange",
        "choice",
        "shuffle",
        "gauss",
        "normalvariate",
        "lognormvariate",
        "expovariate",
        "vonmisesvariate",
        "gammavariate",
        "betavariate",
        "paretovariate",
        "weibullvariate",
        "getrandbits",
    ]:
        if hasattr(_random, attr):
            setattr(restricted, attr, getattr(_random, attr))

    # Wrapped functions with size limits
    def safe_randbytes(n: int) -> bytes:
        if n > MAX_RANDOM_BYTES:
            raise SecurityError(
                f"random.randbytes() size {n} exceeds limit of {MAX_RANDOM_BYTES} bytes"
            )
        return _random.randbytes(n)

    def safe_choices(population, weights=None, *, cum_weights=None, k=1):
        if k > MAX_RANDOM_SEQUENCE:
            raise SecurityError(f"random.choices() k={k} exceeds limit of {MAX_RANDOM_SEQUENCE}")
        return _random.choices(population, weights, cum_weights=cum_weights, k=k)

    def safe_sample(population, k, *, counts=None):
        if k > MAX_RANDOM_SEQUENCE:
            raise SecurityError(f"random.sample() k={k} exceeds limit of {MAX_RANDOM_SEQUENCE}")
        return _random.sample(population, k, counts=counts)

    restricted.randbytes = safe_randbytes
    restricted.choices = safe_choices
    restricted.sample = safe_sample

    return restricted


def _create_restricted_functools() -> ModuleType:
    """Create a restricted functools module with bounded lru_cache."""
    restricted = ModuleType("functools")

    # Copy safe attributes
    for attr in [
        "partial",
        "partialmethod",
        "reduce",
        "wraps",
        "WRAPPER_ASSIGNMENTS",
        "WRAPPER_UPDATES",
        "total_ordering",
        "cmp_to_key",
        "cached_property",
        "singledispatch",
        "singledispatchmethod",
        "update_wrapper",
    ]:
        if hasattr(_functools, attr):
            setattr(restricted, attr, getattr(_functools, attr))

    # Wrapped lru_cache that enforces maxsize
    def safe_lru_cache(maxsize=128, typed=False):
        if maxsize is None or maxsize > MAX_LRU_CACHE_SIZE:
            raise SecurityError(
                f"functools.lru_cache() maxsize must be <= {MAX_LRU_CACHE_SIZE} "
                f"(got {maxsize}). Unbounded caches can exhaust memory."
            )
        return _functools.lru_cache(maxsize=maxsize, typed=typed)

    # Also wrap cache() which is lru_cache(maxsize=None)
    def blocked_cache(user_function=None):
        raise SecurityError(
            "functools.cache() is not allowed - it has unbounded memory growth. "
            f"Use lru_cache(maxsize={MAX_LRU_CACHE_SIZE}) instead."
        )

    restricted.lru_cache = safe_lru_cache
    restricted.cache = blocked_cache

    return restricted


def _create_restricted_re() -> ModuleType:
    """Create a restricted re module with input size limits to prevent ReDoS."""
    restricted = ModuleType("re")

    # Copy constants and flags
    for attr in [
        "A",
        "ASCII",
        "DEBUG",
        "I",
        "IGNORECASE",
        "L",
        "LOCALE",
        "M",
        "MULTILINE",
        "NOFLAG",
        "S",
        "DOTALL",
        "U",
        "UNICODE",
        "VERBOSE",
        "X",
        "error",
        "Pattern",
        "Match",
        "RegexFlag",
    ]:
        if hasattr(_re, attr):
            setattr(restricted, attr, getattr(_re, attr))

    def _check_limits(pattern, string=None):
        """Check pattern and string against limits."""
        pattern_str = pattern if isinstance(pattern, str) else pattern.pattern
        if len(pattern_str) > MAX_REGEX_PATTERN_LENGTH:
            raise SecurityError(
                f"Regex pattern length {len(pattern_str)} exceeds limit of {MAX_REGEX_PATTERN_LENGTH}"
            )
        if string is not None and len(string) > MAX_REGEX_INPUT_LENGTH:
            raise SecurityError(
                f"Regex input length {len(string)} exceeds limit of {MAX_REGEX_INPUT_LENGTH}"
            )

    def safe_compile(pattern, flags=0):
        _check_limits(pattern)
        return _re.compile(pattern, flags)

    def safe_search(pattern, string, flags=0):
        _check_limits(pattern, string)
        return _re.search(pattern, string, flags)

    def safe_match(pattern, string, flags=0):
        _check_limits(pattern, string)
        return _re.match(pattern, string, flags)

    def safe_fullmatch(pattern, string, flags=0):
        _check_limits(pattern, string)
        return _re.fullmatch(pattern, string, flags)

    def safe_split(pattern, string, maxsplit=0, flags=0):
        _check_limits(pattern, string)
        return _re.split(pattern, string, maxsplit, flags)

    def safe_findall(pattern, string, flags=0):
        _check_limits(pattern, string)
        return _re.findall(pattern, string, flags)

    def safe_finditer(pattern, string, flags=0):
        _check_limits(pattern, string)
        return _re.finditer(pattern, string, flags)

    def safe_sub(pattern, repl, string, count=0, flags=0):
        _check_limits(pattern, string)
        return _re.sub(pattern, repl, string, count=count, flags=flags)

    def safe_subn(pattern, repl, string, count=0, flags=0):
        _check_limits(pattern, string)
        return _re.subn(pattern, repl, string, count=count, flags=flags)

    def safe_escape(pattern):
        if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
            raise SecurityError(
                f"Regex escape input length {len(pattern)} exceeds limit of {MAX_REGEX_PATTERN_LENGTH}"
            )
        return _re.escape(pattern)

    def safe_purge():
        return _re.purge()

    restricted.compile = safe_compile
    restricted.search = safe_search
    restricted.match = safe_match
    restricted.fullmatch = safe_fullmatch
    restricted.split = safe_split
    restricted.findall = safe_findall
    restricted.finditer = safe_finditer
    restricted.sub = safe_sub
    restricted.subn = safe_subn
    restricted.escape = safe_escape
    restricted.purge = safe_purge

    return restricted


def _create_restricted_decimal() -> ModuleType:
    """Create a restricted decimal module with precision limits."""
    restricted = ModuleType("decimal")

    # Copy safe classes and constants
    for attr in [
        "Decimal",
        "Context",
        "localcontext",
        "getcontext",
        "setcontext",
        "DefaultContext",
        "BasicContext",
        "ExtendedContext",
        "DecimalException",
        "Clamped",
        "InvalidOperation",
        "DivisionByZero",
        "Inexact",
        "Rounded",
        "Subnormal",
        "Overflow",
        "Underflow",
        "FloatOperation",
        "ROUND_UP",
        "ROUND_DOWN",
        "ROUND_CEILING",
        "ROUND_FLOOR",
        "ROUND_HALF_UP",
        "ROUND_HALF_DOWN",
        "ROUND_HALF_EVEN",
        "ROUND_05UP",
        "MAX_PREC",
        "MAX_EMAX",
        "MIN_EMIN",
        "MIN_ETINY",
    ]:
        if hasattr(_decimal, attr):
            setattr(restricted, attr, getattr(_decimal, attr))

    # Override getcontext to enforce precision limits
    _original_getcontext = _decimal.getcontext

    def safe_getcontext():
        ctx = _original_getcontext()
        if ctx.prec > MAX_DECIMAL_PRECISION:
            ctx.prec = MAX_DECIMAL_PRECISION
        return ctx

    def safe_setcontext(ctx):
        if ctx.prec > MAX_DECIMAL_PRECISION:
            raise SecurityError(
                f"Decimal precision {ctx.prec} exceeds limit of {MAX_DECIMAL_PRECISION}"
            )
        return _decimal.setcontext(ctx)

    def safe_localcontext(ctx=None):
        if ctx is not None and ctx.prec > MAX_DECIMAL_PRECISION:
            raise SecurityError(
                f"Decimal precision {ctx.prec} exceeds limit of {MAX_DECIMAL_PRECISION}"
            )
        return _decimal.localcontext(ctx)

    restricted.getcontext = safe_getcontext
    restricted.setcontext = safe_setcontext
    restricted.localcontext = safe_localcontext

    return restricted


# Create singleton instances of restricted modules
RESTRICTED_TIME = _create_restricted_time()
RESTRICTED_RANDOM = _create_restricted_random()
RESTRICTED_FUNCTOOLS = _create_restricted_functools()
RESTRICTED_RE = _create_restricted_re()
RESTRICTED_DECIMAL = _create_restricted_decimal()

# Map module names to their restricted versions
RESTRICTED_MODULE_MAP: dict[str, ModuleType] = {
    "time": RESTRICTED_TIME,
    "random": RESTRICTED_RANDOM,
    "functools": RESTRICTED_FUNCTOOLS,
    "re": RESTRICTED_RE,
    "decimal": RESTRICTED_DECIMAL,
}


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
    # Security error for sandbox violations
    "SecurityError": SecurityError,
}


def create_safe_import(allowed_imports: frozenset[str]) -> Callable:
    """Create a safe import function that only allows whitelisted modules.

    Args:
        allowed_imports: Set of module names that are allowed to be imported.

    Returns:
        A restricted __import__ function that returns restricted module versions
        for modules in RESTRICTED_MODULE_MAP.
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

        # Return restricted version if available
        if module_name in RESTRICTED_MODULE_MAP and name == module_name:
            return RESTRICTED_MODULE_MAP[module_name]

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

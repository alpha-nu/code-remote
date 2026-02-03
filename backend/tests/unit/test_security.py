"""Unit tests for the security module."""

import pytest

from executor.security import (
    MAX_DECIMAL_PRECISION,
    MAX_LRU_CACHE_SIZE,
    MAX_RANDOM_BYTES,
    MAX_RANDOM_SEQUENCE,
    MAX_REGEX_INPUT_LENGTH,
    MAX_REGEX_PATTERN_LENGTH,
    RESTRICTED_DECIMAL,
    RESTRICTED_FUNCTOOLS,
    RESTRICTED_RANDOM,
    RESTRICTED_RE,
    RESTRICTED_TIME,
    SecurityError,
    is_code_safe,
    validate_code,
)


class TestAllowedImports:
    """Tests for allowed imports."""

    def test_math_import_allowed(self):
        """Test that math module can be imported."""
        code = "import math"
        violations = validate_code(code)
        assert len(violations) == 0

    def test_json_import_allowed(self):
        """Test that json module can be imported."""
        code = "import json"
        violations = validate_code(code)
        assert len(violations) == 0

    def test_collections_import_allowed(self):
        """Test that collections module can be imported."""
        code = "from collections import defaultdict"
        violations = validate_code(code)
        assert len(violations) == 0

    def test_itertools_import_allowed(self):
        """Test that itertools module can be imported."""
        code = "from itertools import combinations"
        violations = validate_code(code)
        assert len(violations) == 0

    def test_typing_import_allowed(self):
        """Test that typing module can be imported."""
        code = "from typing import List, Dict"
        violations = validate_code(code)
        assert len(violations) == 0


class TestBlockedImports:
    """Tests for blocked imports."""

    def test_os_import_blocked(self):
        """Test that os module cannot be imported."""
        code = "import os"
        violations = validate_code(code)
        assert len(violations) == 1
        assert "os" in violations[0].message

    def test_subprocess_import_blocked(self):
        """Test that subprocess module cannot be imported."""
        code = "import subprocess"
        violations = validate_code(code)
        assert len(violations) == 1

    def test_socket_import_blocked(self):
        """Test that socket module cannot be imported."""
        code = "import socket"
        violations = validate_code(code)
        assert len(violations) == 1

    def test_sys_import_blocked(self):
        """Test that sys module cannot be imported."""
        code = "import sys"
        violations = validate_code(code)
        assert len(violations) == 1

    def test_from_os_import_blocked(self):
        """Test that from os import is blocked."""
        code = "from os import path"
        violations = validate_code(code)
        assert len(violations) == 1

    def test_requests_import_blocked(self):
        """Test that requests module cannot be imported."""
        code = "import requests"
        violations = validate_code(code)
        assert len(violations) == 1

    def test_urllib_import_blocked(self):
        """Test that urllib module cannot be imported."""
        code = "import urllib"
        violations = validate_code(code)
        assert len(violations) == 1


class TestBlockedBuiltins:
    """Tests for blocked built-in functions."""

    def test_eval_blocked(self):
        """Test that eval() is blocked."""
        code = "eval('1 + 1')"
        violations = validate_code(code)
        assert len(violations) == 1
        assert "eval" in violations[0].message

    def test_exec_blocked(self):
        """Test that exec() is blocked."""
        code = "exec('x = 1')"
        violations = validate_code(code)
        assert len(violations) == 1
        assert "exec" in violations[0].message

    def test_open_blocked(self):
        """Test that open() is blocked."""
        code = "open('/etc/passwd')"
        violations = validate_code(code)
        assert len(violations) == 1
        assert "open" in violations[0].message

    def test_compile_blocked(self):
        """Test that compile() is blocked."""
        code = "compile('x = 1', '<string>', 'exec')"
        violations = validate_code(code)
        assert len(violations) == 1

    def test___import___blocked(self):
        """Test that __import__() is blocked."""
        code = "__import__('os')"
        violations = validate_code(code)
        assert len(violations) == 1


class TestDangerousAttributes:
    """Tests for dangerous attribute access."""

    def test___class___blocked(self):
        """Test that __class__ access is blocked."""
        code = "x = ''.__class__"
        violations = validate_code(code)
        assert len(violations) == 1

    def test___subclasses___blocked(self):
        """Test that __subclasses__ access is blocked."""
        code = "x = object.__subclasses__()"
        violations = validate_code(code)
        assert len(violations) == 1

    def test___globals___blocked(self):
        """Test that __globals__ access is blocked."""
        code = "x = func.__globals__"
        violations = validate_code(code)
        assert len(violations) == 1


class TestSafeCode:
    """Tests for safe code patterns."""

    def test_simple_arithmetic(self):
        """Test that simple arithmetic is allowed."""
        code = "x = 1 + 2 * 3"
        is_safe, violations = is_code_safe(code)
        assert is_safe
        assert len(violations) == 0

    def test_function_definition(self):
        """Test that function definitions are allowed."""
        code = """
def add(a, b):
    return a + b

result = add(1, 2)
"""
        is_safe, violations = is_code_safe(code)
        assert is_safe

    def test_class_definition(self):
        """Test that class definitions are allowed."""
        code = """
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
"""
        is_safe, violations = is_code_safe(code)
        assert is_safe

    def test_list_comprehension(self):
        """Test that list comprehensions are allowed."""
        code = "squares = [x**2 for x in range(10)]"
        is_safe, violations = is_code_safe(code)
        assert is_safe

    def test_safe_imports_with_code(self):
        """Test code with safe imports."""
        code = """
import math
import json
from collections import Counter

data = Counter([1, 2, 2, 3])
result = math.sqrt(sum(data.values()))
"""
        is_safe, violations = is_code_safe(code)
        assert is_safe


class TestSyntaxErrors:
    """Tests for syntax error handling."""

    def test_syntax_error_detected(self):
        """Test that syntax errors are properly reported."""
        code = "def foo(:"
        is_safe, violations = is_code_safe(code)
        assert not is_safe
        assert len(violations) == 1
        assert "Syntax error" in violations[0].message


class TestMultipleViolations:
    """Tests for code with multiple violations."""

    def test_multiple_bad_imports(self):
        """Test that multiple bad imports are all caught."""
        code = """
import os
import subprocess
import socket
"""
        violations = validate_code(code)
        assert len(violations) == 3

    def test_mixed_violations(self):
        """Test code with mixed violation types."""
        code = """
import os
eval('1 + 1')
x = ''.__class__
"""
        violations = validate_code(code)
        assert len(violations) == 3


class TestRestrictedTimeModule:
    """Tests for the restricted time module."""

    def test_sleep_is_blocked(self):
        """Test that time.sleep() raises SecurityError."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_TIME.sleep(1)
        assert "time.sleep()" in str(exc_info.value)
        assert "not allowed" in str(exc_info.value)

    def test_time_functions_work(self):
        """Test that safe time functions work."""
        # These should not raise
        assert isinstance(RESTRICTED_TIME.time(), float)
        assert isinstance(RESTRICTED_TIME.monotonic(), float)
        assert isinstance(RESTRICTED_TIME.perf_counter(), float)

    def test_time_formatting_works(self):
        """Test that time formatting functions work."""
        import time

        now = time.time()
        # These should not raise
        gm = RESTRICTED_TIME.gmtime(now)
        assert gm is not None
        formatted = RESTRICTED_TIME.strftime("%Y-%m-%d", gm)
        assert len(formatted) == 10


class TestRestrictedRandomModule:
    """Tests for the restricted random module."""

    def test_randbytes_within_limit(self):
        """Test that randbytes works within limit."""
        result = RESTRICTED_RANDOM.randbytes(100)
        assert len(result) == 100

    def test_randbytes_exceeds_limit(self):
        """Test that randbytes raises error when exceeding limit."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_RANDOM.randbytes(MAX_RANDOM_BYTES + 1)
        assert "exceeds limit" in str(exc_info.value)

    def test_choices_within_limit(self):
        """Test that choices works within limit."""
        result = RESTRICTED_RANDOM.choices([1, 2, 3], k=100)
        assert len(result) == 100

    def test_choices_exceeds_limit(self):
        """Test that choices raises error when exceeding limit."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_RANDOM.choices([1, 2, 3], k=MAX_RANDOM_SEQUENCE + 1)
        assert "exceeds limit" in str(exc_info.value)

    def test_sample_within_limit(self):
        """Test that sample works within limit."""
        population = list(range(1000))
        result = RESTRICTED_RANDOM.sample(population, k=100)
        assert len(result) == 100

    def test_sample_exceeds_limit(self):
        """Test that sample raises error when exceeding limit."""
        population = list(range(MAX_RANDOM_SEQUENCE + 10))
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_RANDOM.sample(population, k=MAX_RANDOM_SEQUENCE + 1)
        assert "exceeds limit" in str(exc_info.value)

    def test_basic_random_functions(self):
        """Test that basic random functions work."""
        assert 0 <= RESTRICTED_RANDOM.random() < 1
        assert isinstance(RESTRICTED_RANDOM.randint(1, 10), int)
        assert RESTRICTED_RANDOM.choice([1, 2, 3]) in [1, 2, 3]


class TestRestrictedFunctoolsModule:
    """Tests for the restricted functools module."""

    def test_lru_cache_with_valid_maxsize(self):
        """Test that lru_cache works with valid maxsize."""

        @RESTRICTED_FUNCTOOLS.lru_cache(maxsize=100)
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        assert fib(10) == 55

    def test_lru_cache_unbounded_blocked(self):
        """Test that unbounded lru_cache is blocked."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_FUNCTOOLS.lru_cache(maxsize=None)
        assert "maxsize" in str(exc_info.value)

    def test_lru_cache_exceeds_limit(self):
        """Test that lru_cache with large maxsize is blocked."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_FUNCTOOLS.lru_cache(maxsize=MAX_LRU_CACHE_SIZE + 1)
        assert "maxsize" in str(exc_info.value)

    def test_cache_is_blocked(self):
        """Test that functools.cache() is blocked."""
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_FUNCTOOLS.cache
            RESTRICTED_FUNCTOOLS.cache(lambda x: x)
        assert "cache()" in str(exc_info.value)

    def test_partial_works(self):
        """Test that functools.partial works."""

        def add(a, b):
            return a + b

        add5 = RESTRICTED_FUNCTOOLS.partial(add, 5)
        assert add5(3) == 8


class TestRestrictedReModule:
    """Tests for the restricted re module."""

    def test_search_within_limits(self):
        """Test that search works within limits."""
        result = RESTRICTED_RE.search(r"\d+", "abc123def")
        assert result is not None
        assert result.group() == "123"

    def test_pattern_too_long(self):
        """Test that overly long patterns are blocked."""
        long_pattern = "a" * (MAX_REGEX_PATTERN_LENGTH + 1)
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_RE.search(long_pattern, "test")
        assert "pattern length" in str(exc_info.value)

    def test_input_too_long(self):
        """Test that overly long inputs are blocked."""
        long_input = "a" * (MAX_REGEX_INPUT_LENGTH + 1)
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_RE.search(r"a", long_input)
        assert "input length" in str(exc_info.value)

    def test_compile_within_limits(self):
        """Test that compile works within limits."""
        pattern = RESTRICTED_RE.compile(r"\d+")
        result = pattern.search("abc123")
        assert result.group() == "123"

    def test_findall_works(self):
        """Test that findall works."""
        result = RESTRICTED_RE.findall(r"\d+", "a1b2c3")
        assert result == ["1", "2", "3"]

    def test_sub_works(self):
        """Test that sub works."""
        result = RESTRICTED_RE.sub(r"\d", "X", "a1b2c3")
        assert result == "aXbXcX"


class TestRestrictedDecimalModule:
    """Tests for the restricted decimal module."""

    def test_basic_decimal_operations(self):
        """Test that basic Decimal operations work."""
        d = RESTRICTED_DECIMAL.Decimal("1.5")
        assert d + RESTRICTED_DECIMAL.Decimal("2.5") == RESTRICTED_DECIMAL.Decimal("4.0")

    def test_precision_limit_enforced_on_setcontext(self):
        """Test that setting excessive precision is blocked."""
        ctx = RESTRICTED_DECIMAL.Context(prec=MAX_DECIMAL_PRECISION + 1)
        with pytest.raises(SecurityError) as exc_info:
            RESTRICTED_DECIMAL.setcontext(ctx)
        assert "precision" in str(exc_info.value)

    def test_getcontext_caps_precision(self):
        """Test that getcontext caps precision if needed."""
        ctx = RESTRICTED_DECIMAL.getcontext()
        assert ctx.prec <= MAX_DECIMAL_PRECISION

"""Unit tests for the security module."""

from executor.security import (
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

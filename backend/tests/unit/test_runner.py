"""Unit tests for the code runner."""

from executor.runner import execute_code


class TestBasicExecution:
    """Tests for basic code execution."""

    def test_simple_print(self):
        """Test that print output is captured."""
        code = 'print("hello world")'
        result = execute_code(code)
        assert result.success
        assert "hello world" in result.stdout

    def test_multiple_prints(self):
        """Test that multiple prints are captured."""
        code = """
print("line 1")
print("line 2")
print("line 3")
"""
        result = execute_code(code)
        assert result.success
        assert "line 1" in result.stdout
        assert "line 2" in result.stdout
        assert "line 3" in result.stdout

    def test_arithmetic(self):
        """Test basic arithmetic operations."""
        code = """
x = 1 + 2
y = x * 3
print(y)
"""
        result = execute_code(code)
        assert result.success
        assert "9" in result.stdout

    def test_string_operations(self):
        """Test string operations."""
        code = """
s = "hello"
print(s.upper())
print(len(s))
"""
        result = execute_code(code)
        assert result.success
        assert "HELLO" in result.stdout
        assert "5" in result.stdout


class TestFunctions:
    """Tests for function definitions and calls."""

    def test_function_definition(self):
        """Test defining and calling a function."""
        code = """
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
"""
        result = execute_code(code)
        assert result.success
        assert "Hello, World!" in result.stdout

    def test_recursive_function(self):
        """Test recursive function (fibonacci)."""
        code = """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

print(fib(10))
"""
        result = execute_code(code)
        assert result.success
        assert "55" in result.stdout


class TestDataStructures:
    """Tests for data structure operations."""

    def test_list_operations(self):
        """Test list operations."""
        code = """
nums = [3, 1, 4, 1, 5, 9]
nums.sort()
print(nums)
print(sum(nums))
"""
        result = execute_code(code)
        assert result.success
        assert "[1, 1, 3, 4, 5, 9]" in result.stdout
        assert "23" in result.stdout

    def test_dict_operations(self):
        """Test dictionary operations."""
        code = """
d = {"a": 1, "b": 2, "c": 3}
print(d["b"])
print(list(d.keys()))
"""
        result = execute_code(code)
        assert result.success
        assert "2" in result.stdout

    def test_set_operations(self):
        """Test set operations."""
        code = """
s1 = {1, 2, 3}
s2 = {2, 3, 4}
print(s1 & s2)
print(s1 | s2)
"""
        result = execute_code(code)
        assert result.success
        assert "{2, 3}" in result.stdout


class TestAllowedImports:
    """Tests for allowed module imports."""

    def test_math_module(self):
        """Test math module operations."""
        code = """
import math
print(math.sqrt(16))
print(math.pi)
"""
        result = execute_code(code)
        assert result.success
        assert "4.0" in result.stdout
        assert "3.14" in result.stdout

    def test_json_module(self):
        """Test json module operations."""
        code = """
import json
data = {"key": "value", "number": 42}
print(json.dumps(data))
"""
        result = execute_code(code)
        assert result.success
        assert "key" in result.stdout
        assert "42" in result.stdout

    def test_collections_module(self):
        """Test collections module operations."""
        code = """
from collections import Counter
words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
count = Counter(words)
print(count.most_common(1))
"""
        result = execute_code(code)
        assert result.success
        assert "apple" in result.stdout

    def test_itertools_module(self):
        """Test itertools module operations."""
        code = """
from itertools import combinations
items = [1, 2, 3]
combos = list(combinations(items, 2))
print(combos)
"""
        result = execute_code(code)
        assert result.success
        assert "(1, 2)" in result.stdout


class TestErrorHandling:
    """Tests for error handling."""

    def test_runtime_error_captured(self):
        """Test that runtime errors are captured."""
        code = """
x = 1 / 0
"""
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "ZeroDivisionError"

    def test_name_error_captured(self):
        """Test that name errors are captured."""
        code = """
print(undefined_variable)
"""
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "NameError"

    def test_type_error_captured(self):
        """Test that type errors are captured."""
        code = """
x = "hello" + 5
"""
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "TypeError"

    def test_index_error_captured(self):
        """Test that index errors are captured."""
        code = """
lst = [1, 2, 3]
print(lst[10])
"""
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "IndexError"


class TestSecurityBlocking:
    """Tests for security blocking."""

    def test_os_import_blocked(self):
        """Test that os import is blocked."""
        code = "import os"
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "SecurityError"
        assert len(result.security_violations) > 0

    def test_subprocess_import_blocked(self):
        """Test that subprocess import is blocked."""
        code = "import subprocess"
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "SecurityError"

    def test_eval_blocked(self):
        """Test that eval is blocked."""
        code = "eval('1 + 1')"
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "SecurityError"

    def test_open_blocked(self):
        """Test that open is blocked."""
        code = "open('/etc/passwd')"
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "SecurityError"


class TestTimeout:
    """Tests for execution timeout."""

    def test_infinite_loop_times_out(self):
        """Test that infinite loops are terminated."""
        code = """
while True:
    pass
"""
        result = execute_code(code, timeout_seconds=1.0)
        assert not result.success
        assert result.timed_out
        assert result.error_type == "TimeoutError"

    def test_long_computation_times_out(self):
        """Test that long computations are terminated."""
        code = """
# Inefficient fibonacci that takes forever
def slow_fib(n):
    if n <= 1:
        return n
    return slow_fib(n-1) + slow_fib(n-2)

slow_fib(100)  # This would take years
"""
        result = execute_code(code, timeout_seconds=1.0)
        assert not result.success
        assert result.timed_out

    def test_fast_code_completes(self):
        """Test that fast code completes within timeout."""
        code = """
result = sum(range(1000))
print(result)
"""
        result = execute_code(code, timeout_seconds=5.0)
        assert result.success
        assert not result.timed_out


class TestExecutionTime:
    """Tests for execution time tracking."""

    def test_execution_time_tracked(self):
        """Test that execution time is tracked."""
        code = 'print("hello")'
        result = execute_code(code)
        assert result.success
        assert result.execution_time_ms > 0
        assert result.execution_time_ms < 5000  # Should be fast


class TestStderrCapture:
    """Tests for stderr capture."""

    def test_stderr_from_exception(self):
        """Test that exceptions don't pollute stderr directly."""
        code = """
raise ValueError("test error")
"""
        result = execute_code(code)
        assert not result.success
        assert result.error_type == "ValueError"
        assert "test error" in result.error

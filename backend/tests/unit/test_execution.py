"""Unit tests for the execution endpoint."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestExecuteEndpoint:
    """Tests for POST /execute endpoint."""

    def test_execute_simple_print(self, client):
        """Test executing a simple print statement."""
        response = client.post(
            "/execute",
            json={"code": 'print("hello world")'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hello world" in data["stdout"]

    def test_execute_arithmetic(self, client):
        """Test executing arithmetic operations."""
        response = client.post(
            "/execute",
            json={"code": "x = 1 + 2\nprint(x * 3)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "9" in data["stdout"]

    def test_execute_with_allowed_import(self, client):
        """Test executing code with allowed imports."""
        response = client.post(
            "/execute",
            json={"code": "import math\nprint(math.sqrt(16))"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "4.0" in data["stdout"]

    def test_execute_blocked_import(self, client):
        """Test that blocked imports fail."""
        response = client.post(
            "/execute",
            json={"code": "import os"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error_type"] == "SecurityError"
        assert len(data["security_violations"]) > 0

    def test_execute_blocked_builtin(self, client):
        """Test that blocked builtins fail."""
        response = client.post(
            "/execute",
            json={"code": "eval('1 + 1')"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error_type"] == "SecurityError"

    def test_execute_runtime_error(self, client):
        """Test that runtime errors are captured."""
        response = client.post(
            "/execute",
            json={"code": "x = 1 / 0"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error_type"] == "ZeroDivisionError"

    def test_execute_syntax_error(self, client):
        """Test that syntax errors are captured."""
        response = client.post(
            "/execute",
            json={"code": "def foo(:"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Syntax error" in data["security_violations"][0]["message"]

    def test_execute_timeout(self, client):
        """Test that timeout is enforced."""
        response = client.post(
            "/execute",
            json={
                "code": "while True: pass",
                "timeout_seconds": 1.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["timed_out"] is True
        assert data["error_type"] == "TimeoutError"

    def test_execute_tracks_execution_time(self, client):
        """Test that execution time is tracked."""
        response = client.post(
            "/execute",
            json={"code": 'print("fast")'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["execution_time_ms"] > 0

    def test_execute_custom_timeout(self, client):
        """Test custom timeout parameter."""
        response = client.post(
            "/execute",
            json={
                "code": 'print("hello")',
                "timeout_seconds": 5.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestExecuteValidation:
    """Tests for request validation."""

    def test_empty_code_rejected(self, client):
        """Test that empty code is rejected."""
        response = client.post(
            "/execute",
            json={"code": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_missing_code_rejected(self, client):
        """Test that missing code field is rejected."""
        response = client.post(
            "/execute",
            json={},
        )
        assert response.status_code == 422

    def test_invalid_timeout_rejected(self, client):
        """Test that invalid timeout is rejected."""
        response = client.post(
            "/execute",
            json={
                "code": 'print("hello")',
                "timeout_seconds": -1,
            },
        )
        assert response.status_code == 422

    def test_timeout_exceeding_max_rejected(self, client):
        """Test that timeout exceeding max is rejected."""
        response = client.post(
            "/execute",
            json={
                "code": 'print("hello")',
                "timeout_seconds": 100.0,  # Max is 30
            },
        )
        assert response.status_code == 422


class TestExecuteComplexCode:
    """Tests for more complex code execution."""

    def test_function_definition_and_call(self, client):
        """Test defining and calling functions."""
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
"""
        response = client.post("/execute", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "120" in data["stdout"]

    def test_class_definition_and_use(self, client):
        """Test defining and using classes."""
        code = """
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
        return self.count

c = Counter()
print(c.increment())
print(c.increment())
print(c.increment())
"""
        response = client.post("/execute", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "1" in data["stdout"]
        assert "2" in data["stdout"]
        assert "3" in data["stdout"]

    def test_list_comprehension(self, client):
        """Test list comprehensions."""
        code = """
squares = [x**2 for x in range(5)]
print(squares)
"""
        response = client.post("/execute", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "[0, 1, 4, 9, 16]" in data["stdout"]

    def test_json_operations(self, client):
        """Test JSON operations with allowed import."""
        code = """
import json
data = {"name": "test", "value": 42}
encoded = json.dumps(data, sort_keys=True)
decoded = json.loads(encoded)
print(decoded["name"], decoded["value"])
"""
        response = client.post("/execute", json={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "test" in data["stdout"]
        assert "42" in data["stdout"]

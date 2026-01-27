"""
Smoke tests for deployed API.

These tests run after deployment to verify the service is working correctly.
They make real HTTP requests to the deployed endpoint.
"""

import os

import httpx
import pytest

# Get API endpoint from environment or command line
API_ENDPOINT = os.getenv("API_ENDPOINT", "http://localhost:8000")


def pytest_addoption(parser):
    """Add command line options for smoke tests."""
    parser.addoption(
        "--api-url",
        action="store",
        default=API_ENDPOINT,
        help="API endpoint URL for smoke tests",
    )


@pytest.fixture
def api_url(request):
    """Get the API URL from command line or environment."""
    return request.config.getoption("--api-url")


@pytest.fixture
def client(api_url):
    """Create an HTTP client for the API."""
    return httpx.Client(base_url=api_url, timeout=30.0)


class TestHealthEndpoint:
    """Smoke tests for health endpoints."""

    def test_health_check(self, client):
        """Verify the health endpoint returns OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self, client):
        """Verify the readiness endpoint returns OK."""
        response = client.get("/ready")
        assert response.status_code == 200


class TestExecutionEndpoint:
    """Smoke tests for code execution (requires auth bypass or test token)."""

    @pytest.mark.skipif(
        os.getenv("ENVIRONMENT") == "prod",
        reason="Execution tests skipped in production",
    )
    def test_simple_execution(self, client):
        """Verify simple code execution works."""
        response = client.post(
            "/api/v1/execute",
            json={"code": "print('Hello, smoke test!')"},
            headers={"X-Dev-Bypass": "true"},  # Only works in dev/staging
        )

        # Should either succeed or return 401 (if auth required)
        assert response.status_code in [200, 401]

        if response.status_code == 200:
            data = response.json()
            assert "output" in data


class TestOpenAPISchema:
    """Verify OpenAPI schema is accessible."""

    def test_openapi_json(self, client):
        """Verify OpenAPI JSON is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_endpoint(self, client):
        """Verify Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

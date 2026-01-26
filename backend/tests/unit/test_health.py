"""Unit tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


def test_health_check_returns_200(client: TestClient) -> None:
    """Health endpoint should return 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_returns_healthy_status(client: TestClient) -> None:
    """Health endpoint should return healthy status."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"


def test_health_check_returns_version(client: TestClient) -> None:
    """Health endpoint should return version."""
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] == "0.1.0"

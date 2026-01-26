"""Unit tests for the analysis endpoint."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.analyzer_service import get_analyzer_service


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class MockAnalyzerService:
    """Mock analyzer service for testing."""

    def __init__(self, available: bool = True):
        self._available = available
        self.mock_result = AsyncMock()
        self.mock_result.time_complexity = "O(n)"
        self.mock_result.space_complexity = "O(1)"
        self.mock_result.time_explanation = "Linear loop"
        self.mock_result.space_explanation = "No extra space"
        self.mock_result.algorithm_identified = "Linear Search"
        self.mock_result.suggestions = ["Use binary search"]
        self.mock_result.error = None

    async def analyze(self, code: str):
        from api.schemas.analysis import AnalyzeResponse

        return AnalyzeResponse(
            success=True,
            time_complexity=self.mock_result.time_complexity,
            space_complexity=self.mock_result.space_complexity,
            time_explanation=self.mock_result.time_explanation,
            space_explanation=self.mock_result.space_explanation,
            algorithm_identified=self.mock_result.algorithm_identified,
            suggestions=self.mock_result.suggestions,
            error=self.mock_result.error,
            available=self._available,
        )

    def is_available(self) -> bool:
        return self._available


class TestAnalyzeEndpoint:
    """Tests for POST /analyze endpoint."""

    def test_analyze_with_mocked_llm(self, client):
        """Test analysis with mocked LLM response."""
        mock_service = MockAnalyzerService(available=True)

        app.dependency_overrides[get_analyzer_service] = lambda: mock_service

        try:
            response = client.post(
                "/analyze",
                json={"code": "for i in range(n): print(i)"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["time_complexity"] == "O(n)"
            assert data["algorithm_identified"] == "Linear Search"
        finally:
            app.dependency_overrides.clear()

    def test_analyze_empty_code_rejected(self, client):
        """Test that empty code is rejected."""
        response = client.post(
            "/analyze",
            json={"code": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_analyze_missing_code_rejected(self, client):
        """Test that missing code field is rejected."""
        response = client.post(
            "/analyze",
            json={},
        )
        assert response.status_code == 422


class TestAnalyzeStatusEndpoint:
    """Tests for GET /analyze/status endpoint."""

    def test_status_when_configured(self, client):
        """Test status when LLM is configured."""
        mock_service = MockAnalyzerService(available=True)
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service

        try:
            response = client.get("/analyze/status")

            assert response.status_code == 200
            data = response.json()
            assert data["available"] is True
            assert data["provider"] == "gemini"
        finally:
            app.dependency_overrides.clear()

    def test_status_when_not_configured(self, client):
        """Test status when LLM is not configured."""
        mock_service = MockAnalyzerService(available=False)
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service

        try:
            response = client.get("/analyze/status")

            assert response.status_code == 200
            data = response.json()
            assert data["available"] is False
            assert data["provider"] is None
        finally:
            app.dependency_overrides.clear()

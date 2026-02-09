"""Unit tests for the analysis endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.auth.dependencies import get_current_user
from api.auth.models import User
from api.main import app
from api.services.analyzer_service import get_analyzer_service
from api.services.database import get_db

# Test user for authenticated requests
TEST_USER = User(
    id="test-user-123",
    email="test@example.com",
    username="testuser",
    groups=None,
)


class MockAnalyzerService:
    """Mock analyzer service for testing."""

    def __init__(self, available: bool = True):
        self._available = available

    async def analyze(self, code: str):
        from api.schemas.analysis import AnalyzeResponse

        return AnalyzeResponse(
            success=True,
            time_complexity="O(n)",
            space_complexity="O(1)",
            narrative="### Algorithm\nLinear Search.\n\n### Time Complexity: O(n)\nSingle pass.\n\n### Space Complexity: O(1)\nConstant space.",
            error=None,
            available=self._available,
            model="gemini-2.0-flash",
        )

    async def analyze_stream(self, code: str):
        from api.schemas.analysis import AnalyzeResponse

        yield "### Algorithm\nLinear Search.\n\n"
        yield "### Time Complexity: O(n)\nSingle pass.\n\n"
        yield "### Space Complexity: O(1)\nConstant space."
        yield AnalyzeResponse(
            success=True,
            time_complexity="O(n)",
            space_complexity="O(1)",
            narrative="### Algorithm\nLinear Search.\n\n### Time Complexity: O(n)\nSingle pass.\n\n### Space Complexity: O(1)\nConstant space.",
            error=None,
            available=self._available,
            model="gemini-2.0-flash",
        )

    def is_available(self) -> bool:
        return self._available


class TestAnalyzeEndpoint:
    """Tests for POST /analyze (sync fallback) endpoint."""

    def test_analyze_with_mocked_llm(self, client):
        """Test analysis with mocked LLM response."""
        mock_service = MockAnalyzerService(available=True)

        app.dependency_overrides[get_current_user] = lambda: TEST_USER
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
            assert data["space_complexity"] == "O(1)"
            assert "Linear Search" in data["narrative"]
        finally:
            app.dependency_overrides.clear()

    def test_analyze_empty_code_rejected(self, authenticated_client):
        """Test that empty code is rejected."""
        response = authenticated_client.post(
            "/analyze",
            json={"code": ""},
        )
        assert response.status_code == 422

    def test_analyze_missing_code_rejected(self, authenticated_client):
        """Test that missing code field is rejected."""
        response = authenticated_client.post(
            "/analyze",
            json={},
        )
        assert response.status_code == 422

    def test_analyze_unauthenticated_returns_401(self, client):
        """Test that unauthenticated request returns 401."""
        response = client.post(
            "/analyze",
            json={"code": "for i in range(n): print(i)"},
        )
        assert response.status_code == 401

    def test_analyze_with_snippet_id_persists_complexity(self, client):
        """Test that analysis with snippet_id persists complexity to snippet."""
        mock_service = MockAnalyzerService(available=True)
        snippet_id = uuid4()

        mock_db = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            with (
                patch("api.routers.analysis.UserService") as MockUserService,
                patch("api.routers.analysis.SnippetService") as MockSnippetService,
            ):
                mock_user_service = AsyncMock()
                mock_db_user = MagicMock()
                mock_db_user.id = uuid4()
                mock_user_service.get_or_create_from_cognito.return_value = mock_db_user
                MockUserService.return_value = mock_user_service

                mock_snippet_service = AsyncMock()
                mock_snippet = MagicMock()
                mock_snippet_service.update.return_value = mock_snippet
                MockSnippetService.return_value = mock_snippet_service

                response = client.post(
                    "/analyze",
                    json={
                        "code": "for i in range(n): print(i)",
                        "snippet_id": str(snippet_id),
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["time_complexity"] == "O(n)"

                mock_snippet_service.update.assert_called_once()
                call_kwargs = mock_snippet_service.update.call_args.kwargs
                assert call_kwargs["snippet_id"] == snippet_id
                assert call_kwargs["time_complexity"] == "O(n)"
                assert call_kwargs["space_complexity"] == "O(1)"
        finally:
            app.dependency_overrides.clear()

    def test_analyze_with_snippet_id_not_found_still_returns_result(self, client):
        """Test that analysis still returns result even if snippet not found."""
        mock_service = MockAnalyzerService(available=True)
        snippet_id = uuid4()

        mock_db = AsyncMock()
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            with (
                patch("api.routers.analysis.UserService") as MockUserService,
                patch("api.routers.analysis.SnippetService") as MockSnippetService,
            ):
                mock_user_service = AsyncMock()
                mock_db_user = MagicMock()
                mock_db_user.id = uuid4()
                mock_user_service.get_or_create_from_cognito.return_value = mock_db_user
                MockUserService.return_value = mock_user_service

                mock_snippet_service = AsyncMock()
                mock_snippet_service.update.return_value = None
                MockSnippetService.return_value = mock_snippet_service

                response = client.post(
                    "/analyze",
                    json={
                        "code": "for i in range(n): print(i)",
                        "snippet_id": str(snippet_id),
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
        finally:
            app.dependency_overrides.clear()


class TestAnalyzeAsyncEndpoint:
    """Tests for POST /analyze/async (streaming) endpoint."""

    def test_analyze_async_returns_job_id(self, client):
        """Test that async endpoint returns a job_id."""
        mock_service = MockAnalyzerService(available=True)

        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service

        try:
            response = client.post(
                "/analyze/async",
                json={
                    "code": "for i in range(n): print(i)",
                    "connection_id": "test-conn-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "streaming"
        finally:
            app.dependency_overrides.clear()

    def test_analyze_async_unauthenticated(self, client):
        """Test that unauthenticated async request returns 401."""
        response = client.post(
            "/analyze/async",
            json={
                "code": "for i in range(n): print(i)",
                "connection_id": "test-conn-123",
            },
        )
        assert response.status_code == 401

    def test_analyze_async_missing_connection_id(self, client):
        """Test that missing connection_id is rejected."""
        mock_service = MockAnalyzerService(available=True)

        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        app.dependency_overrides[get_analyzer_service] = lambda: mock_service

        try:
            response = client.post(
                "/analyze/async",
                json={"code": "for i in range(n): print(i)"},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


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

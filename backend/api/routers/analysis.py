"""Analysis endpoint for code complexity."""

from fastapi import APIRouter, Depends

from api.auth import User, get_current_user
from api.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from api.services.analyzer_service import AnalyzerService, get_analyzer_service

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(
    request: AnalyzeRequest,
    user: User = Depends(get_current_user),
    analyzer: AnalyzerService = Depends(get_analyzer_service),
) -> AnalyzeResponse:
    """Analyze Python code complexity using LLM.

    Requires authentication. Returns time and space complexity
    analysis with explanations. Requires GEMINI_API_KEY to be configured.
    """
    return await analyzer.analyze(request.code)


@router.get("/analyze/status")
async def analysis_status(
    analyzer: AnalyzerService = Depends(get_analyzer_service),
) -> dict:
    """Check if complexity analysis is available.

    This endpoint is public (no auth required).
    Returns whether the LLM provider is configured.
    """
    return {
        "available": analyzer.is_available(),
        "provider": "gemini" if analyzer.is_available() else None,
    }

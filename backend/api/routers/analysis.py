"""Analysis endpoint for code complexity."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.auth.models import User as CognitoUser
from api.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from api.services.analyzer_service import AnalyzerService, get_analyzer_service
from api.services.database import get_db
from api.services.snippet_service import SnippetService
from api.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(
    request: AnalyzeRequest,
    user: CognitoUser = Depends(get_current_user),
    analyzer: AnalyzerService = Depends(get_analyzer_service),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze Python code complexity using LLM.

    Requires authentication. Returns time and space complexity
    analysis with explanations. Requires GEMINI_API_KEY to be configured.

    If snippet_id is provided and analysis succeeds, the complexity
    results are persisted to the snippet.
    """
    result = await analyzer.analyze(request.code)

    # Persist complexity to snippet if provided and analysis succeeded
    if request.snippet_id and result.success:
        try:
            # Get database user
            user_service = UserService(db)
            db_user = await user_service.get_or_create_from_cognito(
                cognito_sub=user.id,
                email=user.email or "",
                username=user.username,
            )

            # Update snippet with complexity results
            snippet_service = SnippetService(db)
            updated = await snippet_service.update(
                snippet_id=request.snippet_id,
                user_id=db_user.id,
                time_complexity=result.time_complexity,
                space_complexity=result.space_complexity,
            )
            if updated:
                logger.info(
                    f"Persisted complexity to snippet {request.snippet_id}: "
                    f"time={result.time_complexity}, space={result.space_complexity}"
                )
            else:
                logger.warning(
                    f"Failed to update snippet {request.snippet_id} - not found or not owned"
                )
        except Exception as e:
            # Don't fail the analysis if persistence fails
            logger.error(f"Failed to persist complexity to snippet: {e}")

    return result


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

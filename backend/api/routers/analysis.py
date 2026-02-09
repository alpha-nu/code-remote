"""Analysis endpoints for code complexity.

Provides two modes matching the execution pattern:
- POST /analyze        — sync HTTP fallback (blocks until LLM finishes)
- POST /analyze/async  — async, streams chunks via WebSocket
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.auth.models import User as CognitoUser
from api.routers.websocket import push_to_connection
from api.schemas.analysis import (
    AnalyzeJobSubmittedResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AsyncAnalyzeRequest,
)
from api.services.analyzer_service import AnalyzerService, get_analyzer_service
from api.services.database import get_db, get_session_factory
from api.services.snippet_service import SnippetService
from api.services.sync_service import SyncService, get_sync_service
from api.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


# ------------------------------------------------------------------
# Sync fallback (matches POST /execute pattern)
# ------------------------------------------------------------------


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_code(
    request: AnalyzeRequest,
    user: CognitoUser = Depends(get_current_user),
    analyzer: AnalyzerService = Depends(get_analyzer_service),
    db: AsyncSession = Depends(get_db),
    sync_service: SyncService | None = Depends(get_sync_service),
) -> AnalyzeResponse:
    """Analyze Python code complexity using LLM (non-streaming).

    Sync HTTP fallback for when WebSocket is unavailable.
    """
    result = await analyzer.analyze(request.code)

    # Persist complexity to snippet if provided and analysis succeeded
    if request.snippet_id and result.success:
        await _persist_complexity(
            db=db,
            sync_service=sync_service,
            user=user,
            snippet_id=request.snippet_id,
            time_complexity=result.time_complexity,
            space_complexity=result.space_complexity,
        )

    return result


# ------------------------------------------------------------------
# Async streaming (matches POST /execute/async pattern)
# ------------------------------------------------------------------


@router.post("/analyze/async", response_model=AnalyzeJobSubmittedResponse)
async def analyze_code_async(
    request: AsyncAnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: CognitoUser = Depends(get_current_user),
    analyzer: AnalyzerService = Depends(get_analyzer_service),
    sync_service: SyncService | None = Depends(get_sync_service),
) -> AnalyzeJobSubmittedResponse:
    """Submit code for streaming complexity analysis via WebSocket.

    Streams Markdown narrative chunks as the LLM generates them,
    then sends a final complete message with structured results.
    """
    job_id = str(uuid.uuid4())

    background_tasks.add_task(
        _stream_analysis,
        job_id=job_id,
        connection_id=request.connection_id,
        code=request.code,
        snippet_id=request.snippet_id,
        user=user,
        analyzer=analyzer,
        sync_service=sync_service,
    )

    return AnalyzeJobSubmittedResponse(job_id=job_id, status="streaming")


async def _stream_analysis(
    job_id: str,
    connection_id: str,
    code: str,
    snippet_id: "uuid.UUID | None",
    user: CognitoUser,
    analyzer: AnalyzerService,
    sync_service: SyncService | None,
) -> None:
    """Stream analysis chunks via WebSocket, then persist results."""
    # Small delay to ensure the HTTP response is sent first
    await asyncio.sleep(0.1)

    # Signal stream start
    await push_to_connection(
        connection_id,
        {
            "type": "analysis_stream_start",
            "job_id": job_id,
        },
    )

    try:
        final_result: AnalyzeResponse | None = None

        async for item in analyzer.analyze_stream(code):
            if isinstance(item, str):
                await push_to_connection(
                    connection_id,
                    {
                        "type": "analysis_stream_chunk",
                        "job_id": job_id,
                        "chunk": item,
                    },
                )
            else:
                # AnalyzeResponse — final parsed result
                final_result = item

        if final_result:
            await push_to_connection(
                connection_id,
                {
                    "type": "analysis_stream_complete",
                    "job_id": job_id,
                    "result": final_result.model_dump(),
                },
            )

            # Persist to snippet (using a fresh DB session for the background task)
            if snippet_id and final_result.success:
                try:
                    session_factory = get_session_factory()
                    async with session_factory() as db:
                        await _persist_complexity(
                            db=db,
                            sync_service=sync_service,
                            user=user,
                            snippet_id=snippet_id,
                            time_complexity=final_result.time_complexity,
                            space_complexity=final_result.space_complexity,
                        )
                        await db.commit()
                except Exception as e:
                    logger.error(f"Failed to persist complexity in background: {e}")
        else:
            await push_to_connection(
                connection_id,
                {
                    "type": "analysis_stream_error",
                    "job_id": job_id,
                    "error": "No result produced by analysis stream",
                },
            )

    except Exception as e:
        logger.error(f"Analysis stream error: {e}")
        await push_to_connection(
            connection_id,
            {
                "type": "analysis_stream_error",
                "job_id": job_id,
                "error": str(e),
            },
        )


# ------------------------------------------------------------------
# Status endpoint (public, no auth)
# ------------------------------------------------------------------


@router.get("/analyze/status")
async def analysis_status(
    analyzer: AnalyzerService = Depends(get_analyzer_service),
) -> dict:
    """Check if complexity analysis is available."""
    return {
        "available": analyzer.is_available(),
        "provider": "gemini" if analyzer.is_available() else None,
    }


# ------------------------------------------------------------------
# Shared persistence helper
# ------------------------------------------------------------------


async def _persist_complexity(
    *,
    db: AsyncSession,
    sync_service: SyncService | None,
    user: CognitoUser,
    snippet_id: "uuid.UUID",
    time_complexity: str,
    space_complexity: str,
) -> None:
    """Persist complexity results to a snippet and enqueue Neo4j sync."""
    try:
        user_service = UserService(db)
        db_user = await user_service.get_or_create_from_cognito(
            cognito_sub=user.id,
            email=user.email or "",
            username=user.username,
        )

        snippet_service = SnippetService(db)
        updated = await snippet_service.update(
            snippet_id=snippet_id,
            user_id=db_user.id,
            time_complexity=time_complexity,
            space_complexity=space_complexity,
        )
        if updated:
            logger.info(
                f"Persisted complexity to snippet {snippet_id}: "
                f"time={time_complexity}, space={space_complexity}"
            )
            if sync_service:
                await sync_service.enqueue_analyzed(
                    snippet_id=str(snippet_id),
                    user_id=str(db_user.id),
                )
        else:
            logger.warning(f"Failed to update snippet {snippet_id} - not found or not owned")
    except Exception as e:
        logger.error(f"Failed to persist complexity to snippet: {e}")

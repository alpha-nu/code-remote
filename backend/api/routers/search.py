"""Search router for semantic and graph search functionality.

Provides unified search using Text-to-Cypher with semantic fallback,
as well as direct complexity filtering for UI-driven queries.
"""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.auth.models import User as CognitoUser
from api.models import User
from api.schemas.search import (
    ComplexityFilterResponse,
    SearchResultItem,
    SimilarSnippetsResponse,
    UnifiedSearchResponse,
)
from api.services.database import get_db
from api.services.neo4j_service import Neo4jService, get_neo4j_driver
from api.services.search_service import get_search_service
from api.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


async def get_db_user(
    cognito_user: CognitoUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get or create database user from Cognito claims."""
    user_service = UserService(db)
    return await user_service.get_or_create_from_cognito(
        cognito_sub=cognito_user.id,
        email=cognito_user.email or "",
        username=cognito_user.username,
    )


@router.get(
    "",
    response_model=UnifiedSearchResponse,
    summary="Unified search with Text-to-Cypher",
)
async def unified_search(
    q: str = Query(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language search query",
    ),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    user: User = Depends(get_db_user),
) -> UnifiedSearchResponse:
    """Perform unified search using Text-to-Cypher with semantic fallback.

    All search queries go through the unified pipeline:
    1. Generate query embedding (always, for fallback)
    2. LLM generates Cypher (may use vector, graph, or both)
    3. If fails or no results → fallback to pure semantic search

    Examples:
    - "sorting algorithms" → LLM uses vector search
    - "my worst code" → LLM uses graph traversal (ORDER BY rank DESC)
    - "worst sorting algorithms" → LLM combines both
    - "efficient Python searching" → Vector + Language + Rank

    Args:
        q: Natural language search query
        limit: Maximum number of results (1-50, default 10)
        user: Authenticated database user

    Returns:
        Matching snippets with method indicator (cypher/semantic)
    """
    search_service = get_search_service()

    try:
        result = await search_service.search(
            query=q,
            user_id=str(user.id),
            limit=limit,
        )

        search_results = [
            SearchResultItem(
                snippet_id=r.get("snippet_id", r.get("id", "")),
                title=r.get("title"),
                language=r.get("language", "python"),
                description=r.get("description"),
                time_complexity=r.get("time_complexity"),
                space_complexity=r.get("space_complexity"),
                score=r.get("score", 1.0),
            )
            for r in result.results
        ]

        return UnifiedSearchResponse(
            query=result.query,
            results=search_results,
            method=result.method,
            total=result.total,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable",
        )


@router.get(
    "/complexity",
    response_model=ComplexityFilterResponse,
    summary="Filter snippets by complexity",
)
async def complexity_filter(
    complexity: str = Query(
        ...,
        description="Complexity notation (e.g., O(n), O(n²), O(1))",
    ),
    type: str = Query(
        "time",
        description="Complexity type: 'time' or 'space'",
        pattern="^(time|space)$",
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    user: User = Depends(get_db_user),
) -> ComplexityFilterResponse:
    """Filter snippets by exact complexity match.

    Used when user clicks on a complexity badge in the UI.
    Direct graph traversal - fast and exact (no LLM needed).

    Examples:
    - complexity=O(n²)&type=time → Quadratic time algorithms
    - complexity=O(1)&type=space → Constant space algorithms

    Args:
        complexity: Complexity notation (e.g., O(n), O(log n))
        type: 'time' or 'space'
        limit: Maximum number of results
        user: Authenticated database user

    Returns:
        Snippets with matching complexity
    """
    driver = get_neo4j_driver()
    try:
        neo4j_service = Neo4jService(driver)

        # Map type to the correct parameter
        complexity_kwargs = {"user_id": str(user.id), "limit": limit}
        if type == "time":
            complexity_kwargs["time_complexity"] = complexity
        else:
            complexity_kwargs["space_complexity"] = complexity

        results = await asyncio.to_thread(
            neo4j_service.get_snippets_by_complexity,
            **complexity_kwargs,
        )

        search_results = [
            SearchResultItem(
                snippet_id=r.get("snippet_id", r.get("id", "")),
                title=r.get("title"),
                language=r.get("language", "python"),
                description=r.get("description"),
                time_complexity=r.get("time_complexity"),
                space_complexity=r.get("space_complexity"),
                score=1.0,  # Exact match
            )
            for r in results
        ]

        return ComplexityFilterResponse(
            complexity_type=type,
            complexity_value=complexity,
            results=search_results,
            total=len(search_results),
        )
    except Exception as e:
        logger.error(f"Complexity filter failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable",
        )


@router.get(
    "/similar/{snippet_id}",
    response_model=SimilarSnippetsResponse,
    summary="Find similar snippets",
)
async def find_similar(
    snippet_id: UUID,
    limit: int = Query(5, ge=1, le=20, description="Max similar snippets"),
    user: User = Depends(get_db_user),
) -> SimilarSnippetsResponse:
    """Find snippets similar to a given snippet.

    Uses vector similarity on snippet embeddings to find related code.

    Args:
        snippet_id: UUID of the source snippet
        limit: Maximum number of similar snippets (1-20, default 5)
        user: Authenticated database user

    Returns:
        List of similar snippets ordered by similarity score
    """
    search_service = get_search_service()

    try:
        results = await search_service.find_similar(
            snippet_id=str(snippet_id),
            user_id=str(user.id),
            limit=limit,
        )

        search_results = [
            SearchResultItem(
                snippet_id=r.get("snippet_id", r.get("id", "")),
                title=r.get("title"),
                language=r.get("language", "python"),
                description=r.get("description"),
                time_complexity=r.get("time_complexity"),
                space_complexity=r.get("space_complexity"),
                score=r.get("score", 0.0),
            )
            for r in results
        ]

        return SimilarSnippetsResponse(
            source_snippet_id=str(snippet_id),
            similar=search_results,
            total=len(search_results),
        )
    except Exception as e:
        logger.error(f"Find similar failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable",
        )

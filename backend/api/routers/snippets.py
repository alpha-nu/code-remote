"""Snippets router - CRUD endpoints for code snippets.

Provides authenticated endpoints for managing user code snippets.
All endpoints require Cognito JWT authentication.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.auth.models import User as CognitoUser
from api.models import Snippet, User
from api.schemas.snippet import (
    SnippetCreate,
    SnippetDeleteResponse,
    SnippetListResponse,
    SnippetResponse,
    SnippetUpdate,
)
from api.services.database import get_db
from api.services.snippet_service import SnippetService
from api.services.user_service import UserService

router = APIRouter(prefix="/snippets", tags=["snippets"])


async def get_db_user(
    cognito_user: CognitoUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get or create database user from Cognito claims.

    This dependency ensures we have a database User record for the
    authenticated Cognito user. Creates on first access.
    """
    user_service = UserService(db)
    return await user_service.get_or_create_from_cognito(
        cognito_sub=cognito_user.id,  # Cognito 'sub' is stored in .id
        email=cognito_user.email or "",
        username=cognito_user.username,
    )


@router.post(
    "",
    response_model=SnippetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new snippet",
)
async def create_snippet(
    request: SnippetCreate,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> SnippetResponse:
    """Create a new code snippet.

    Requires authentication. The snippet is associated with the
    authenticated user.

    Args:
        request: Snippet creation data
        user: Authenticated database user
        db: Database session

    Returns:
        The created snippet
    """
    service = SnippetService(db)
    snippet = await service.create(
        user_id=user.id,
        code=request.code,
        title=request.title,
        language=request.language,
        description=request.description,
    )
    return SnippetResponse.model_validate(snippet)


@router.get(
    "",
    response_model=SnippetListResponse,
    summary="List user snippets",
)
async def list_snippets(
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> SnippetListResponse:
    """List all snippets for the authenticated user.

    Returns paginated results, ordered by updated_at descending
    (most recently modified first).

    Args:
        user: Authenticated database user
        db: Database session
        limit: Maximum number of items (1-100, default 50)
        offset: Number to skip for pagination

    Returns:
        Paginated list of snippets
    """
    service = SnippetService(db)
    snippets = await service.list_by_user(user.id, limit=limit, offset=offset)

    # Get total count for pagination
    count_query = select(func.count()).select_from(Snippet).where(Snippet.user_id == user.id)
    result = await db.execute(count_query)
    total = result.scalar() or 0

    return SnippetListResponse(
        items=[SnippetResponse.model_validate(s) for s in snippets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{snippet_id}",
    response_model=SnippetResponse,
    summary="Get a snippet by ID",
)
async def get_snippet(
    snippet_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> SnippetResponse:
    """Get a specific snippet by ID.

    Only returns snippets owned by the authenticated user.

    Args:
        snippet_id: UUID of the snippet
        user: Authenticated database user
        db: Database session

    Returns:
        The snippet if found

    Raises:
        HTTPException: 404 if snippet not found or not owned by user
    """
    service = SnippetService(db)
    snippet = await service.get_by_id(snippet_id, user_id=user.id)

    if snippet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snippet not found",
        )

    return SnippetResponse.model_validate(snippet)


@router.put(
    "/{snippet_id}",
    response_model=SnippetResponse,
    summary="Update a snippet",
)
async def update_snippet(
    snippet_id: uuid.UUID,
    request: SnippetUpdate,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> SnippetResponse:
    """Update an existing snippet.

    Only updates snippets owned by the authenticated user.
    Only provided fields are updated.

    Args:
        snippet_id: UUID of the snippet
        request: Fields to update
        user: Authenticated database user
        db: Database session

    Returns:
        The updated snippet

    Raises:
        HTTPException: 404 if snippet not found or not owned by user
    """
    service = SnippetService(db)
    snippet = await service.update(
        snippet_id=snippet_id,
        user_id=user.id,
        code=request.code,
        title=request.title,
        language=request.language,
        description=request.description,
    )

    if snippet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snippet not found",
        )

    return SnippetResponse.model_validate(snippet)


@router.delete(
    "/{snippet_id}",
    response_model=SnippetDeleteResponse,
    summary="Delete a snippet",
)
async def delete_snippet(
    snippet_id: uuid.UUID,
    user: User = Depends(get_db_user),
    db: AsyncSession = Depends(get_db),
) -> SnippetDeleteResponse:
    """Delete a snippet.

    Only deletes snippets owned by the authenticated user.

    Args:
        snippet_id: UUID of the snippet
        user: Authenticated database user
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: 404 if snippet not found or not owned by user
    """
    service = SnippetService(db)
    deleted = await service.delete(snippet_id=snippet_id, user_id=user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snippet not found",
        )

    return SnippetDeleteResponse(deleted=True, id=snippet_id)

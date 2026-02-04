"""Snippet service - CRUD operations for code snippets.

Provides async CRUD operations for snippets using SQLAlchemy.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Snippet

logger = logging.getLogger(__name__)


class SnippetService:
    """Service for managing code snippets."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        code: str,
        title: str | None = None,
        language: str = "python",
        description: str | None = None,
        is_starred: bool = False,
    ) -> Snippet:
        """Create a new snippet.

        Args:
            user_id: Owner's user ID
            code: The code content
            title: Optional title
            language: Programming language (default: python)
            description: Optional description
            is_starred: Whether snippet is starred (default: False)

        Returns:
            The created Snippet
        """
        snippet = Snippet(
            user_id=user_id,
            code=code,
            title=title,
            language=language,
            description=description,
            is_starred=is_starred,
        )
        self.db.add(snippet)
        await self.db.flush()
        await self.db.refresh(snippet)
        logger.info(f"Created snippet {snippet.id} for user {user_id}")
        return snippet

    async def get_by_id(
        self,
        snippet_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Snippet | None:
        """Get a snippet by ID.

        Args:
            snippet_id: The snippet UUID
            user_id: If provided, only return if owned by this user

        Returns:
            The Snippet if found, None otherwise
        """
        query = select(Snippet).where(Snippet.id == snippet_id)
        if user_id is not None:
            query = query.where(Snippet.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Snippet]:
        """List snippets for a user.

        Args:
            user_id: Owner's user ID
            limit: Maximum number to return (default: 50)
            offset: Number to skip (default: 0)

        Returns:
            List of Snippets, ordered by starred first then updated_at descending
        """
        query = (
            select(Snippet)
            .where(Snippet.user_id == user_id)
            .order_by(Snippet.is_starred.desc(), Snippet.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_summaries_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Snippet]:
        """List snippet summaries for a user (excludes code for efficiency).

        Args:
            user_id: Owner's user ID
            limit: Maximum number to return (default: 50)
            offset: Number to skip (default: 0)

        Returns:
            List of Snippets with code deferred, ordered by starred first then updated_at descending
        """
        # Select all columns except 'code' for efficiency
        query = (
            select(
                Snippet.id,
                Snippet.user_id,
                Snippet.title,
                Snippet.language,
                Snippet.description,
                Snippet.execution_count,
                Snippet.is_starred,
                Snippet.last_execution_at,
                Snippet.created_at,
                Snippet.updated_at,
            )
            .where(Snippet.user_id == user_id)
            .order_by(Snippet.is_starred.desc(), Snippet.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.mappings().all())

    async def update(
        self,
        snippet_id: uuid.UUID,
        user_id: uuid.UUID,
        code: str | None = None,
        title: str | None = None,
        language: str | None = None,
        description: str | None = None,
        is_starred: bool | None = None,
    ) -> Snippet | None:
        """Update an existing snippet.

        Args:
            snippet_id: The snippet UUID
            user_id: Owner's user ID (for authorization)
            code: New code content (if changing)
            title: New title (if changing)
            language: New language (if changing)
            description: New description (if changing)
            is_starred: New starred status (if changing)

        Returns:
            The updated Snippet if found and owned by user, None otherwise
        """
        snippet = await self.get_by_id(snippet_id, user_id)
        if snippet is None:
            return None

        if code is not None:
            snippet.code = code
        if title is not None:
            snippet.title = title
        if language is not None:
            snippet.language = language
        if description is not None:
            snippet.description = description
        if is_starred is not None:
            snippet.is_starred = is_starred

        await self.db.flush()
        await self.db.refresh(snippet)
        logger.info(f"Updated snippet {snippet_id}")
        return snippet

    async def delete(
        self,
        snippet_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a snippet.

        Args:
            snippet_id: The snippet UUID
            user_id: Owner's user ID (for authorization)

        Returns:
            True if deleted, False if not found or not owned by user
        """
        snippet = await self.get_by_id(snippet_id, user_id)
        if snippet is None:
            return False

        await self.db.delete(snippet)
        await self.db.flush()
        logger.info(f"Deleted snippet {snippet_id}")
        return True

    async def record_execution(
        self,
        snippet_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Snippet | None:
        """Record that a snippet was executed.

        Increments execution_count and updates last_execution_at.

        Args:
            snippet_id: The snippet UUID
            user_id: Owner's user ID (for authorization)

        Returns:
            The updated Snippet if found, None otherwise
        """
        snippet = await self.get_by_id(snippet_id, user_id)
        if snippet is None:
            return None

        snippet.execution_count += 1
        snippet.last_execution_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(snippet)
        return snippet

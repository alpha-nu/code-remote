"""User service - sync Cognito users to PostgreSQL.

Handles user creation/update on first API interaction after Cognito authentication.
This ensures we have a local user record with a UUID for foreign keys.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import User

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user records synced from Cognito."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def get_or_create_from_cognito(
        self,
        cognito_sub: str,
        email: str,
        username: str | None = None,
    ) -> User:
        """Get existing user or create from Cognito claims.

        Called on each authenticated API request to ensure user exists.
        Updates last_login timestamp on every call.

        Args:
            cognito_sub: Cognito user ID (sub claim from JWT)
            email: User email from Cognito
            username: Optional username

        Returns:
            The User record (existing or newly created)
        """
        # Try to find existing user by Cognito sub
        user = await self.get_by_cognito_sub(cognito_sub)

        if user is None:
            # Create new user
            user = User(
                cognito_sub=cognito_sub,
                email=email,
                username=username or email.split("@")[0],
            )
            self.db.add(user)
            logger.info(f"Created new user from Cognito: {email}")
        else:
            # Update email if changed (Cognito allows email changes)
            if user.email != email:
                user.email = email
                logger.info(f"Updated email for user {user.id}")

        # Always update last_login
        user.last_login = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_cognito_sub(self, cognito_sub: str) -> User | None:
        """Get user by Cognito sub claim.

        Args:
            cognito_sub: The Cognito user ID

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(User.cognito_sub == cognito_sub)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by internal UUID.

        Args:
            user_id: Internal user UUID

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email address

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

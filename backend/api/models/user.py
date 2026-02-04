"""User model - synced from Cognito.

Users are created/updated on first API interaction after Cognito authentication.
The sub (Cognito user ID) is the primary identifier.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User record synced from AWS Cognito.

    Attributes:
        id: Internal UUID primary key
        cognito_sub: Cognito user ID (sub claim) - unique identifier
        email: User email from Cognito
        username: Optional username (defaults to email)
        last_login: Timestamp of last API access
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    cognito_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Cognito user ID (sub claim)",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last API access timestamp",
    )

    # Relationships
    snippets: Mapped[list["Snippet"]] = relationship(  # noqa: F821
        "Snippet",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

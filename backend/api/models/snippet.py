"""Snippet model - code snippets with execution history.

Stores user code snippets with optional titles and language metadata.
Phase 9.2 will add vector embeddings via pgvector extension.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base, TimestampMixin


class Snippet(Base, TimestampMixin):
    """Code snippet with metadata.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to User
        title: Optional snippet title
        language: Programming language (default: python)
        code: The actual code content
        description: Optional description
        last_execution_at: When code was last executed
        execution_count: Number of times executed
    """

    __tablename__ = "snippets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="python",
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    last_execution_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="snippets",
    )

    def __repr__(self) -> str:
        title = self.title or "untitled"
        return f"<Snippet(id={self.id}, title={title})>"

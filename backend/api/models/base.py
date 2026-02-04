"""SQLAlchemy declarative base and common mixins.

This module provides the base class for all models and common mixins
for timestamps and other shared functionality.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides automatic table naming and common configuration.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805 - cls is correct for declared_attr
        """Generate table name from class name (CamelCase -> snake_case)."""
        import re

        name = cls.__name__
        # Convert CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)

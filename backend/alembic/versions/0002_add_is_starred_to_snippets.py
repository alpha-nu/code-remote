"""Add is_starred column to snippets

Revision ID: 0002
Revises: 0001_initial_schema
Create Date: 2026-02-04

Add is_starred boolean column and composite index for efficient
starred-first ordering in snippet listings.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_is_starred"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_starred column and composite index."""
    # Add is_starred column with default False
    op.add_column(
        "snippets",
        sa.Column(
            "is_starred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Create composite index for efficient starred-first ordering
    # This index supports: WHERE user_id = ? ORDER BY is_starred DESC, updated_at DESC
    op.create_index(
        "ix_snippets_user_starred_updated",
        "snippets",
        ["user_id", sa.text("is_starred DESC"), sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    """Remove is_starred column and composite index."""
    op.drop_index("ix_snippets_user_starred_updated", table_name="snippets")
    op.drop_column("snippets", "is_starred")

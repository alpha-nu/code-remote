"""Add complexity fields to snippets

Revision ID: 0003
Revises: 0002_add_is_starred
Create Date: 2026-02-04

Add time_complexity and space_complexity columns to snippets table.
These will be populated by Phase 9.2 Neo4j semantic search integration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_complexity_fields"
down_revision: str | None = "0002_add_is_starred"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add complexity columns."""
    op.add_column(
        "snippets",
        sa.Column(
            "time_complexity",
            sa.String(50),
            nullable=True,
            comment="Time complexity from analysis (e.g., O(n), O(n²))",
        ),
    )
    op.add_column(
        "snippets",
        sa.Column(
            "space_complexity",
            sa.String(50),
            nullable=True,
            comment="Space complexity from analysis (e.g., O(1), O(n))",
        ),
    )


def downgrade() -> None:
    """Remove complexity columns."""
    op.drop_column("snippets", "space_complexity")
    op.drop_column("snippets", "time_complexity")

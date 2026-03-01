"""Add source_created_at and composite_score columns to news_items.

Revision ID: 010
Revises: 009
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_items",
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "news_items",
        sa.Column("composite_score", sa.Float(), nullable=True),
    )
    op.create_index("idx_news_items_composite_score", "news_items", ["composite_score"])


def downgrade() -> None:
    op.drop_index("idx_news_items_composite_score", table_name="news_items")
    op.drop_column("news_items", "composite_score")
    op.drop_column("news_items", "source_created_at")

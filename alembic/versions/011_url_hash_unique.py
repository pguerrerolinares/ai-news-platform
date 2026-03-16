"""Add partial unique index on url_hash after cleaning duplicates.

Revision ID: 011
Revises: 010
"""

from __future__ import annotations

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Delete duplicate url_hash rows, keeping the one with
    # highest composite_score (tiebreak: most recent created_at).
    op.execute("""
        DELETE FROM news_items
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY url_hash
                           ORDER BY composite_score DESC NULLS LAST,
                                    created_at DESC
                       ) AS rn
                FROM news_items
                WHERE url_hash IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)

    # Step 2: Create partial unique index (NULLs excluded)
    op.create_index(
        "uix_news_items_url_hash",
        "news_items",
        ["url_hash"],
        unique=True,
        postgresql_where="url_hash IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uix_news_items_url_hash", table_name="news_items")

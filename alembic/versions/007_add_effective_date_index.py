"""add effective date functional index

Revision ID: 007
Revises: 006
Create Date: 2026-02-27
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX idx_news_items_effective_date "
        "ON news_items (COALESCE(published_at, created_at) DESC)"
    )


def downgrade() -> None:
    op.drop_index("idx_news_items_effective_date", table_name="news_items")

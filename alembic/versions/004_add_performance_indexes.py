"""add performance indexes

Revision ID: 004
Revises: 003
Create Date: 2026-02-21
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX idx_news_items_score ON news_items (score DESC NULLS LAST)")
    op.execute(
        "CREATE INDEX idx_news_items_source_date ON news_items (source, published_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_news_items_topic_date ON news_items (topic, published_at DESC)"
    )
    op.execute("CREATE INDEX idx_news_items_created_at ON news_items (created_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_news_items_created_at", table_name="news_items")
    op.drop_index("idx_news_items_topic_date", table_name="news_items")
    op.drop_index("idx_news_items_source_date", table_name="news_items")
    op.drop_index("idx_news_items_score", table_name="news_items")

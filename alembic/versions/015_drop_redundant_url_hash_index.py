"""Drop redundant non-unique idx_news_items_url_hash index.

The partial unique index uix_news_items_url_hash already covers non-NULL
url_hash lookups. The non-unique index is redundant storage.

Revision ID: 015
Revises: 014
"""

from __future__ import annotations

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_news_items_url_hash", table_name="news_items")


def downgrade() -> None:
    op.create_index("idx_news_items_url_hash", "news_items", ["url_hash"])

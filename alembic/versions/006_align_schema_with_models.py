"""Align DB schema with ORM models.

Fixes:
- NOT NULL on columns with server_default that were missing nullable=False
- Recreate DESC indexes as simple ASC (model defines them without DESC,
  PostgreSQL can scan ASC indexes backwards for ORDER BY ... DESC)

Revision ID: 006
Revises: 005
Create Date: 2026-02-27
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

# Columns that have server_default but were created without explicit nullable=False.
# The ORM model uses Mapped[T] (not Optional), meaning NOT NULL is intended.
_NULLABLE_FIXES = [
    ("news_items", "trending", "BOOLEAN"),
    ("news_items", "created_at", "TIMESTAMP WITH TIME ZONE"),
    ("daily_briefings", "generated_at", "TIMESTAMP WITH TIME ZONE"),
    ("item_embeddings", "created_at", "TIMESTAMP WITH TIME ZONE"),
    ("otp_codes", "used", "BOOLEAN"),
    ("otp_codes", "created_at", "TIMESTAMP WITH TIME ZONE"),
    ("raw_extractions", "extracted_at", "TIMESTAMP WITH TIME ZONE"),
    ("users", "created_at", "TIMESTAMP WITH TIME ZONE"),
]

# Indexes originally created with DESC that the model defines as simple ASC.
# PostgreSQL can backward-scan ASC indexes, so ORDER BY ... DESC still uses them.
_INDEX_REWRITES = [
    ("idx_news_items_date", "news_items", "published_at"),
    ("idx_news_items_score", "news_items", "score"),
    ("idx_news_items_source_date", "news_items", "source, published_at"),
    ("idx_news_items_topic_date", "news_items", "topic, published_at"),
    ("idx_news_items_created_at", "news_items", "created_at"),
]


def upgrade() -> None:
    # 1. Fix nullable on columns with server_default
    for table, column, col_type in _NULLABLE_FIXES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")

    # 2. Recreate DESC indexes as simple indexes (match ORM model)
    for idx_name, table, columns in _INDEX_REWRITES:
        op.execute(f"DROP INDEX IF EXISTS {idx_name}")
        op.execute(f"CREATE INDEX {idx_name} ON {table} ({columns})")


def downgrade() -> None:
    # Restore DESC indexes
    desc_defs = {
        "idx_news_items_date": ("news_items", "published_at DESC"),
        "idx_news_items_score": ("news_items", "score DESC NULLS LAST"),
        "idx_news_items_source_date": ("news_items", "source, published_at DESC"),
        "idx_news_items_topic_date": ("news_items", "topic, published_at DESC"),
        "idx_news_items_created_at": ("news_items", "created_at DESC"),
    }
    for idx_name, (table, columns) in desc_defs.items():
        op.execute(f"DROP INDEX IF EXISTS {idx_name}")
        op.execute(f"CREATE INDEX {idx_name} ON {table} ({columns})")

    # Restore nullable
    for table, column, col_type in _NULLABLE_FIXES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL")

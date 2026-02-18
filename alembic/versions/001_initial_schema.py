"""Initial schema: news_items, daily_briefings, item_embeddings.

Revision ID: 001
Revises: None
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # news_items
    op.create_table(
        "news_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("topic", sa.String(50), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("dev_value_score", sa.Float(), nullable=True),
        sa.Column("credibility_score", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("trending", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("content_hash", sa.Text(), unique=True, nullable=True),
        sa.Column("url_hash", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.CheckConstraint(
            "topic IS NULL OR topic IN ("
            "'modelos','papers','agentes','productos',"
            "'herramientas','open_source','regulacion')",
            name="valid_topic",
        ),
    )

    op.create_index("idx_news_items_date", "news_items", [sa.text("published_at DESC")])
    op.create_index("idx_news_items_topic", "news_items", ["topic"])
    op.create_index("idx_news_items_source", "news_items", ["source"])
    op.create_index("idx_news_items_content_hash", "news_items", ["content_hash"])
    op.create_index("idx_news_items_url_hash", "news_items", ["url_hash"])
    op.execute(
        "CREATE INDEX idx_news_items_fts ON news_items USING gin("
        "to_tsvector('english', title || ' ' || coalesce(summary, '')"
        " || ' ' || coalesce(full_text, '')))"
    )

    # daily_briefings
    op.create_table(
        "daily_briefings",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("total_items", sa.Integer(), nullable=True),
        sa.Column("items_extracted", sa.Integer(), nullable=True),
        sa.Column("items_after_dedup", sa.Integer(), nullable=True),
        sa.Column("items_filtered", sa.Integer(), nullable=True),
        sa.Column("trending_count", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("sources_used", JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # item_embeddings (Milestone 4 — table created now, populated later)
    op.create_table(
        "item_embeddings",
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("news_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("model", sa.Text(), primary_key=True, nullable=False),
        # Placeholder: replaced with vector(768) in Milestone 4
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("item_embeddings")
    op.drop_table("daily_briefings")
    op.execute("DROP INDEX IF EXISTS idx_news_items_fts")
    op.drop_index("idx_news_items_url_hash", table_name="news_items")
    op.drop_index("idx_news_items_content_hash", table_name="news_items")
    op.drop_index("idx_news_items_source", table_name="news_items")
    op.drop_index("idx_news_items_topic", table_name="news_items")
    op.drop_index("idx_news_items_date", table_name="news_items")
    op.drop_table("news_items")
    op.execute("DROP EXTENSION IF EXISTS vector")

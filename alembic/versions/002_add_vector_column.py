"""Add vector(1536) column and HNSW index to item_embeddings.

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("item_embeddings", "embedding")
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX ix_item_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_item_embeddings_hnsw")
    op.drop_column("item_embeddings", "embedding")
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding TEXT")

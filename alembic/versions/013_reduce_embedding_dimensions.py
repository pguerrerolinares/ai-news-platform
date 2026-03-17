"""Reduce embedding dimensions from 1536 to 512.

text-embedding-3-small supports native dimensions=512 with ~1% precision loss.
Saves ~3x storage. Existing embeddings are deleted and will be regenerated
by the pipeline's embed_new_items step (~7K items, ~$0.01).

Revision ID: 013
Revises: 012
"""

from __future__ import annotations

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop HNSW index (cannot alter column with index)
    op.drop_index("idx_embeddings_hnsw", table_name="item_embeddings")

    # 2. Delete all existing 1536-dim embeddings (will be regenerated as 512-dim)
    op.execute("DELETE FROM item_embeddings")

    # 3. Alter column from vector(1536) to vector(512)
    op.execute("ALTER TABLE item_embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding vector(512)")

    # 4. Recreate HNSW index for 512-dim vectors
    op.execute(
        "CREATE INDEX idx_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_embeddings_hnsw", table_name="item_embeddings")
    op.execute("DELETE FROM item_embeddings")
    op.execute("ALTER TABLE item_embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE item_embeddings ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX idx_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

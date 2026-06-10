"""Drop duplicate HNSW index on item_embeddings.

ix_item_embeddings_hnsw (from migration 002) and idx_embeddings_hnsw (from ORM)
are functionally identical. Drop the migration-created one to save ~56MB.

Revision ID: 012
Revises: 011
"""

from __future__ import annotations

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF EXISTS: idempotent for fresh/divergent DBs that never had the
    # duplicate index (it originated from migration 002 on older deployments).
    op.execute("DROP INDEX IF EXISTS ix_item_embeddings_hnsw")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX ix_item_embeddings_hnsw ON item_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

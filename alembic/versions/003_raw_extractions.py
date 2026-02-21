"""Add raw_extractions table for historical backfill.

Revision ID: 003
Revises: 002
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_extractions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("raw_json", JSONB, nullable=False),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("backfill_batch", sa.String(50)),
        sa.UniqueConstraint("source", "source_id", name="uq_raw_source_id"),
    )
    op.create_index("idx_raw_source", "raw_extractions", ["source"])
    op.create_index("idx_raw_batch", "raw_extractions", ["backfill_batch"])


def downgrade() -> None:
    op.drop_index("idx_raw_batch", table_name="raw_extractions")
    op.drop_index("idx_raw_source", table_name="raw_extractions")
    op.drop_table("raw_extractions")

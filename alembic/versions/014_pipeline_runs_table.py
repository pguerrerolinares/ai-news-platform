"""Add pipeline_runs table for per-execution stats.

Revision ID: 014
Revises: 013
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sources", JSONB(), nullable=False),
        sa.Column("items_extracted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_after_dedup", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_seen_filtered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_classified", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_validated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_stored", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(12), nullable=True),
    )
    op.create_index("idx_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.create_index("idx_pipeline_runs_status", "pipeline_runs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("idx_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

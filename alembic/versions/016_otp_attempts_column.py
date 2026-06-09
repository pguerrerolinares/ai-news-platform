"""Add attempts column to otp_codes for per-code brute-force lockout.

A submitted OTP is burned (marked used) after MAX_OTP_ATTEMPTS wrong guesses,
so the 6-digit space cannot be brute-forced across distributed IPs.

Revision ID: 016
Revises: 015
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "otp_codes",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("otp_codes", "attempts")

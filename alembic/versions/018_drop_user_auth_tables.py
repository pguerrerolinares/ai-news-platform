"""Drop user_auth tables (users, otp_codes, webauthn_credentials).

The platform is now guest-only (web pública guest-only): login via OTP+Resend
email and WebAuthn/passkeys are discontinued, along with the registered-user
and admin-user model. Guest tokens (POST /api/auth/guest) and require_auth
(used by the still-protected but currently inaccessible POST /api/chat)
remain untouched — they don't depend on these tables.

Reversibility note: downgrade() recreates the schema (accumulated from
005+006+009+016) with its indexes, but NOT the data. That's acceptable here:
these are credentials/codes for a discontinued auth system, not business
data. If a pre-deploy dump is wanted, `pg_dump -t users -t otp_codes
-t webauthn_credentials` before running this migration.

Revision ID: 018
Revises: 017
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop order respects FK: webauthn_credentials -> users first, then
    # otp_codes (no FKs), then users.
    op.drop_table("webauthn_credentials")
    op.drop_table("otp_codes")
    op.drop_table("users")


def downgrade() -> None:
    # Recreate accumulated schema from 005 (users, otp_codes) + 006 (NOT NULL
    # fixes) + 009 (webauthn_credentials) + 016 (otp_codes.attempts). Schema
    # only — data is not restored (see module docstring).
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'reader'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'reader')", name="valid_role"),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_otp_codes_lookup", "otp_codes", ["email", "used", "expires_at"])

    op.create_table(
        "webauthn_credentials",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("device_name", sa.Text(), nullable=False),
        sa.Column("transports", JSONB(), nullable=True),
        sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_webauthn_user_id", "webauthn_credentials", ["user_id"])

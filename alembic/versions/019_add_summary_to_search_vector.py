"""Add summary to search_vector; search.py drops its ILIKE fallback.

The FTS trigger (008, redefined by 017) indexes title+full_text+source but
search.py additionally OR'd in an ILIKE fallback over title/source/summary
to compensate for summary not being indexed — an un-indexed OR that forces a
sequential scan (revision-2026-09-13.md #1). This migration adds summary to
the indexed columns so the GIN index alone is sufficient; search.py drops
the ILIKE fallback in the same change. Also drops the dead
``idx_news_items_fts`` (001) that tripled the backfill cost (unused since
F-16, excluded from ``alembic check``).

Revision ID: 019
Revises: 018
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

# Read by tests/integration/conftest.py (loaded by path — see helper there)
# to install the same function against the ephemeral test schema, which is
# built via Base.metadata.create_all and never runs migrations.
SEARCH_VECTOR_FUNCTION_SQL = """
    CREATE OR REPLACE FUNCTION public.news_items_search_trigger() RETURNS trigger AS $$
    BEGIN
      NEW.search_vector := to_tsvector('simple',
        coalesce(NEW.title, '') || ' ' ||
        coalesce(NEW.full_text, '') || ' ' ||
        coalesce(NEW.summary, '') || ' ' ||
        coalesce(NEW.source, ''));
      RETURN NEW;
    END $$ LANGUAGE plpgsql
"""

SEARCH_VECTOR_BACKFILL_SQL = """
    UPDATE news_items
    SET search_vector = to_tsvector('simple',
        coalesce(title, '') || ' ' ||
        coalesce(full_text, '') || ' ' ||
        coalesce(summary, '') || ' ' ||
        coalesce(source, ''))
"""

LEGACY_FTS_INDEX = "idx_news_items_fts"
# Literal from 001_initial_schema.py:66 — unused since F-16, only recreated on downgrade.
LEGACY_FTS_INDEX_SQL = (
    f"CREATE INDEX IF NOT EXISTS {LEGACY_FTS_INDEX} ON news_items USING gin("
    "to_tsvector('english', title || ' ' || coalesce(summary, '')"
    " || ' ' || coalesce(full_text, '')))"
)


def upgrade() -> None:
    # Drop before the backfill: every UPDATE row is a non-HOT update (the GIN
    # index is on an expression), so this dead index alone was ~3.6x the
    # backfill cost (measured: 113.6s with it vs 31.0s without, 11k rows).
    op.execute(f"DROP INDEX IF EXISTS {LEGACY_FTS_INDEX}")
    op.execute(SEARCH_VECTOR_FUNCTION_SQL)
    op.execute(SEARCH_VECTOR_BACKFILL_SQL)


def downgrade() -> None:
    # Restore EXACTLY the 017 function/backfill (simple config, no summary).
    op.execute("""
        CREATE OR REPLACE FUNCTION public.news_items_search_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('simple',
            coalesce(NEW.title, '') || ' ' ||
            coalesce(NEW.full_text, '') || ' ' ||
            coalesce(NEW.source, ''));
          RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        UPDATE news_items
        SET search_vector = to_tsvector('simple',
            coalesce(title, '') || ' ' ||
            coalesce(full_text, '') || ' ' ||
            coalesce(source, ''))
    """)
    # Recreate after the re-backfill so the downgrade doesn't pay for it either.
    op.execute(LEGACY_FTS_INDEX_SQL)

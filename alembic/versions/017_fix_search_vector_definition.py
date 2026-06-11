"""Fix search_vector trigger: use simple config + title/full_text/source columns.

The previous trigger used 'english' config and only title+summary. This
migration aligns the stored column with search.py's actual query intent:
'simple' config over title+full_text+source. Backfills existing rows.

Revision ID: 017
Revises: 016
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replace the trigger function body: 'simple' config, title+full_text+source
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

    # Backfill all existing rows with the new definition
    op.execute("""
        UPDATE news_items
        SET search_vector = to_tsvector('simple',
            coalesce(title, '') || ' ' ||
            coalesce(full_text, '') || ' ' ||
            coalesce(source, ''))
    """)


def downgrade() -> None:
    # Restore the original trigger function body: 'english' config, title+summary
    op.execute("""
        CREATE OR REPLACE FUNCTION public.news_items_search_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('english',
            coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, ''));
          RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)

    # Backfill back to the original definition
    op.execute("""
        UPDATE news_items
        SET search_vector = to_tsvector('english',
            coalesce(title, '') || ' ' || coalesce(summary, ''))
    """)

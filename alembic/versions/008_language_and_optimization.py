"""Language standardization, search vector, and index optimization.

Revision ID: 008
Revises: 007
Create Date: 2026-02-28
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. New columns
    op.execute("ALTER TABLE news_items ADD COLUMN IF NOT EXISTS language VARCHAR(5) NOT NULL DEFAULT 'en'")
    op.execute("ALTER TABLE news_items ADD COLUMN IF NOT EXISTS search_vector tsvector")

    # 2. search_vector auto-update trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION news_items_search_trigger() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector := to_tsvector('english',
            coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, ''));
          RETURN NEW;
        END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_news_items_search
          BEFORE INSERT OR UPDATE OF title, summary ON news_items
          FOR EACH ROW EXECUTE FUNCTION news_items_search_trigger()
    """)

    # 3. GIN index on search_vector
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_search "
        "ON news_items USING gin(search_vector)"
    )

    # 4. HNSW index on embeddings
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw "
        "ON item_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    # 5. Partial index for trending
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_trending_date "
        "ON news_items (COALESCE(published_at, created_at) DESC) "
        "WHERE trending = true"
    )

    # 6. Drop duplicate index (unique constraint already covers this)
    op.execute("DROP INDEX IF EXISTS idx_news_items_content_hash")

    # 7. Update topic check constraint to English names
    op.execute("ALTER TABLE news_items DROP CONSTRAINT IF EXISTS valid_topic")
    op.execute("""
        ALTER TABLE news_items ADD CONSTRAINT valid_topic
        CHECK (topic IS NULL OR topic IN (
            'models', 'papers', 'agents', 'products',
            'tools', 'open_source', 'regulation'
        ))
    """)


def downgrade() -> None:
    # Restore Spanish topic constraint
    op.execute("ALTER TABLE news_items DROP CONSTRAINT IF EXISTS valid_topic")
    op.execute("""
        ALTER TABLE news_items ADD CONSTRAINT valid_topic
        CHECK (topic IS NULL OR topic IN (
            'modelos', 'papers', 'agentes', 'productos',
            'herramientas', 'open_source', 'regulacion'
        ))
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_news_items_search ON news_items")
    op.execute("DROP FUNCTION IF EXISTS news_items_search_trigger()")
    op.execute("DROP INDEX IF EXISTS idx_news_items_search")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_news_items_trending_date")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_content_hash "
        "ON news_items (content_hash)"
    )
    op.execute("ALTER TABLE news_items DROP COLUMN IF EXISTS search_vector")
    op.execute("ALTER TABLE news_items DROP COLUMN IF EXISTS language")

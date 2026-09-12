"""Alembic environment configuration for async SQLAlchemy."""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, text

from alembic import context
from src.core.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override URL from environment if available
db_url = os.environ.get("DATABASE_URL_SYNC", config.get_main_option("sqlalchemy.url"))

# Arbitrary fixed key for pg_advisory_lock, scoped to this app's migrations.
# Concurrent redeploys (finding #11) each run `alembic upgrade head`; without
# a lock, two processes racing on DDL (e.g. both creating alembic_version)
# fail with a UniqueViolation. pg_advisory_lock blocks the second process
# until the first finishes, at which point it finds the DB already at head
# and exits cleanly.
_MIGRATION_LOCK_KEY = 8_675_309

# Indexes created via raw SQL that can't be represented in ORM models
_EXCLUDED_INDEXES = {"idx_news_items_fts", "ix_item_embeddings_hnsw"}


def include_object(obj, name, type_, reflected, compare_to):
    """Exclude PostgreSQL-specific indexes from autogenerate comparison.

    GIN (FTS) and HNSW (pgvector) indexes are created via raw SQL in
    migrations and have no SQLAlchemy ORM representation.
    """
    return not (type_ == "index" and name in _EXCLUDED_INDEXES)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database.

    Wrapped in a session-level pg_advisory_lock so two concurrent redeploys
    (e.g. Coolify rolling out two containers) don't race on DDL -- the
    second process blocks until the first releases the lock, then finds the
    DB already at head and is a no-op.
    """
    connectable = create_engine(db_url)

    with connectable.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
        # pg_advisory_lock is session-scoped, not transactional -- commit to
        # close the implicit (autobegin) transaction it opened, so Alembic's
        # own begin_transaction() below starts from a clean slate.
        connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
            )

            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY}
            )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

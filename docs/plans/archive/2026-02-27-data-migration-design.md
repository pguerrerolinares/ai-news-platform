# Data Migration: Historical Data to Production

> **Status**: Completed (2026-02-27)
> **Date**: 2026-02-27
> **Approach**: Selective pg_dump/pg_restore (data-only, single-transaction)

## Context

Migrate ~6,374 news items, ~6,374 embeddings, and ~21,526 raw extractions from the
local development database to production. Production had ~171 recent items from the
live pipeline. Decision: truncate production data and do a clean restore.

## What Was Migrated

| Table | Rows Restored |
|---|---|
| `news_items` | 6,374 |
| `item_embeddings` | 6,374 |
| `raw_extractions` | 21,526 |
| `daily_briefings` | 0 (empty locally) |

**Excluded**: `users`, `otp_codes`, `alembic_version` (production-specific).

## Procedure (as executed)

### 1. Verify local data

```bash
# Inside local docker db container
psql -U ainews -d ainews -c "
SELECT 'news_items' AS tabla, COUNT(*) FROM news_items
UNION ALL SELECT 'item_embeddings', COUNT(*) FROM item_embeddings
UNION ALL SELECT 'raw_extractions', COUNT(*) FROM raw_extractions;"
```

Result: 6,374 / 6,374 / 21,526. Date range: 2026-02-21.

### 2. Dump local (data-only, binary format, selected tables)

```bash
# Run inside the local db container
pg_dump -U ainews -d ainews \
  -Fc \
  --data-only \
  --no-owner \
  --no-privileges \
  -t news_items \
  -t item_embeddings \
  -t raw_extractions \
  -f /tmp/ainews_historical_data.dump
```

Result: 57MB dump file.

### 3. Transfer to server

```bash
# Copy from container to host
docker cp <db_container>:/tmp/ainews_historical_data.dump /tmp/

# Upload to production server
scp /tmp/ainews_historical_data.dump user@server:/tmp/
```

### 4. Backup production (on server)

```bash
# Identify container name
docker ps --format '{{.Names}}\t{{.Image}}' | grep pgvector
export DB_CONTAINER="<db-container-name>"

# IMPORTANT: use -i not -t when piping output
docker exec -i $DB_CONTAINER pg_dump -U ainews ainews \
  --no-owner --no-privileges | gzip > /tmp/ainews_prod_backup_pre_migration.sql.gz
```

### 5. Stop services

```bash
export API_CONTAINER="<api-container-name>"
export PIPELINE_CONTAINER="<pipeline-cron-container-name>"
docker stop $API_CONTAINER $PIPELINE_CONTAINER
```

### 6. Truncate production data and restore

```bash
# Truncate (CASCADE removes embeddings via FK)
docker exec -i $DB_CONTAINER psql -U ainews -d ainews -c "
TRUNCATE news_items CASCADE;
TRUNCATE raw_extractions;
"

# Copy dump into container
docker cp /tmp/ainews_historical_data.dump $DB_CONTAINER:/tmp/

# Restore
docker exec -i $DB_CONTAINER pg_restore \
  -U ainews -d ainews \
  --data-only \
  --disable-triggers \
  --single-transaction \
  /tmp/ainews_historical_data.dump
```

### 7. Verify

```bash
docker exec -i $DB_CONTAINER psql -U ainews -d ainews -c "
SELECT 'news_items' AS tabla, COUNT(*) FROM news_items
UNION ALL SELECT 'item_embeddings', COUNT(*) FROM item_embeddings
UNION ALL SELECT 'raw_extractions', COUNT(*) FROM raw_extractions;"
```

Expected: 6,374 / 6,374 / 21,526.

### 8. Restart services

```bash
docker start $API_CONTAINER $PIPELINE_CONTAINER
```

### 9. Cleanup

```bash
docker exec -i $DB_CONTAINER rm /tmp/ainews_historical_data.dump
rm /tmp/ainews_historical_data.dump
# Keep backup a few days, then: rm /tmp/ainews_prod_backup_pre_migration.sql.gz
```

## Lessons Learned

1. **Coolify deployments**: No `docker-compose.yml` accessible — use `docker exec` directly
   with container names (find via `docker ps`).
2. **`docker exec -t` vs `-i`**: Use `-i` (not `-t`) when piping output (e.g., pg_dump | gzip).
   `-t` allocates a TTY that breaks pipe redirection.
3. **`pg_dump --inserts` fails with pgvector**: SQL text INSERT format corrupts vector data
   (1536-dim floats). Always use binary format (`-Fc`) for tables with vector columns.
4. **pg_dump table order is alphabetical**: With binary format (`-Fc`), `pg_restore` handles
   FK ordering via `--disable-triggers`. With `--inserts` (plain SQL), tables are dumped
   alphabetically — `item_embeddings` before `news_items` — causing FK violations.
5. **Simplest approach wins**: When production data is expendable, TRUNCATE + clean restore
   is far simpler than merge strategies (ON CONFLICT, staging tables, etc.).

## Rollback

If needed, restore from the pre-migration backup:

```bash
docker stop $API_CONTAINER $PIPELINE_CONTAINER
gunzip -c /tmp/ainews_prod_backup_pre_migration.sql.gz | \
  docker exec -i $DB_CONTAINER psql -U ainews -d ainews
docker start $API_CONTAINER $PIPELINE_CONTAINER
```

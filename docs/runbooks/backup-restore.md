# Backup & Restore Runbook

## Automated Backups

Backups run daily at 2:00 UTC via cron:
```bash
0 2 * * * cd /opt/ai-news-platform && ./scripts/backup.sh
```

### What's backed up
- Full PostgreSQL dump (all tables, data, schema)
- Compressed with gzip
- Uploaded to Backblaze B2 (if configured)
- Local copies retained for 7 days

### Backup location
- Local: `/tmp/ainews-backups/ainews_YYYYMMDD_HHMMSS.sql.gz`
- Remote: `s3://B2_BUCKET/backups/ainews_YYYYMMDD_HHMMSS.sql.gz`

## Manual Backup
```bash
cd /opt/ai-news-platform
./scripts/backup.sh
```

## Restore from Backup

### 1. Download backup
```bash
# From Backblaze B2
b2 download-file-by-name B2_BUCKET backups/ainews_20260217_020000.sql.gz /tmp/restore.sql.gz

# Or use local copy
cp /tmp/ainews-backups/ainews_20260217_020000.sql.gz /tmp/restore.sql.gz
```

### 2. Stop services
```bash
cd /opt/ai-news-platform
docker compose stop api pipeline
```

### 3. Restore
```bash
gunzip -c /tmp/restore.sql.gz | docker compose exec -T db psql -U ainews ainews
```

### 4. Restart services
```bash
docker compose up -d api
./scripts/health_check.sh
```

## Verify Backup Integrity

Periodically test restores:
```bash
# Create a test database
docker compose exec db createdb -U ainews ainews_test_restore
gunzip -c /tmp/ainews-backups/latest.sql.gz | docker compose exec -T db psql -U ainews ainews_test_restore

# Verify data
docker compose exec db psql -U ainews ainews_test_restore -c "SELECT count(*) FROM news_items;"

# Cleanup
docker compose exec db dropdb -U ainews ainews_test_restore
```

## Alerts

Backup script failures trigger Telegram alerts via AlertService.

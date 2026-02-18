#!/usr/bin/env bash
# Database backup: pg_dump -> gzip -> Backblaze B2
# Usage: ./scripts/backup.sh
# Requires: POSTGRES_USER, POSTGRES_DB, B2_BUCKET (optional)
set -euo pipefail

BACKUP_DIR="/tmp/ainews-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="${BACKUP_DIR}/ainews_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Starting backup..."
docker compose exec -T db pg_dump \
    -U "${POSTGRES_USER:-ainews}" \
    "${POSTGRES_DB:-ainews}" \
    --no-owner \
    --no-privileges \
    | gzip > "$DUMP_FILE"

SIZE_MB=$(du -m "$DUMP_FILE" | cut -f1)
echo "Backup created: $DUMP_FILE (${SIZE_MB}MB)"

# Upload to Backblaze B2 if configured
if [ -n "${B2_BUCKET:-}" ]; then
    echo "Uploading to Backblaze B2..."
    b2 upload-file "$B2_BUCKET" "$DUMP_FILE" "backups/ainews_${TIMESTAMP}.sql.gz"
    echo "Upload complete."
fi

# Clean up local backups older than 7 days
find "$BACKUP_DIR" -name "ainews_*.sql.gz" -mtime +7 -delete 2>/dev/null || true

echo "Backup completed successfully."

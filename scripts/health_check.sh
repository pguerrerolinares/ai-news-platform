#!/usr/bin/env bash
# Health check for post-deploy verification.
# Usage: ./scripts/health_check.sh [url] [timeout_seconds]
set -euo pipefail

URL="${1:-http://localhost:8000/health}"
TIMEOUT="${2:-60}"
INTERVAL=5
ELAPSED=0

echo "Health check: $URL (timeout: ${TIMEOUT}s)"

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    RESPONSE=$(curl -sf "$URL" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        echo "Health check PASSED (${ELAPSED}s)"
        exit 0
    fi
    echo "  Waiting... (${ELAPSED}s / ${TIMEOUT}s)"
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Health check FAILED after ${TIMEOUT}s"
exit 1

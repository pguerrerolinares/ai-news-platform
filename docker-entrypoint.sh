#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

# If a custom command is passed (e.g. pipeline-scheduler.sh), run it
if [ $# -gt 0 ]; then
    echo "Running custom command: $*"
    exec "$@"
fi

echo "Starting API server..."
exec uvicorn src.api.app:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers "${API_WORKERS:-2}"

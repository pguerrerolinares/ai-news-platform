#!/usr/bin/env bash
# Simple pipeline scheduler using sleep loop.
# Runs the pipeline once at startup, then daily at PIPELINE_SCHEDULE_HOUR.
set -e

SCHEDULE_HOUR="${PIPELINE_SCHEDULE_HOUR:-8}"

echo "Pipeline scheduler started. Will run daily at ${SCHEDULE_HOUR}:00 UTC."

# Run once at startup
echo "Running initial pipeline..."
python -m src.main || echo "Initial pipeline run failed (non-fatal)."

while true; do
    CURRENT_HOUR=$(date -u +%H)
    CURRENT_MIN=$(date -u +%M)

    if [ "$CURRENT_HOUR" -eq "$SCHEDULE_HOUR" ] && [ "$CURRENT_MIN" -eq "0" ]; then
        echo "Scheduled run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        python -m src.main || echo "Pipeline run failed (non-fatal)."
        # Sleep 61 seconds to avoid running twice in the same minute
        sleep 61
    else
        sleep 30
    fi
done

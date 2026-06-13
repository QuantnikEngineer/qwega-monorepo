#!/bin/bash
set -uo pipefail

PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"

echo "=== Starting application ==="

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --loop uvloop \
    --timeout-keep-alive 30

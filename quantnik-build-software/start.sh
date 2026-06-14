#!/bin/bash
# Start the build-software orchestrator, loading credentials from .env
# Usage: ./start.sh [port]
set -e
cd "$(dirname "$0")"

PORT="${1:-8083}"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in credentials."
  exit 1
fi

# Export all non-comment, non-empty lines from .env
set -a
source .env
set +a

export PORT="$PORT"

echo "Starting Quantnik Build-Software Orchestrator on port $PORT..."
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --no-access-log

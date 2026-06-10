#!/bin/sh
set -e

# Run DB migrations if alembic is present
if command -v alembic >/dev/null 2>&1 && [ -f ./alembic.ini ]; then
  echo "Running alembic migrations..."
  alembic upgrade head || echo "alembic upgrade failed; continuing"
fi

echo "Starting uvicorn..."
HOST="${SERVER_HOST:-0.0.0.0}"
PORT="${SERVER_PORT:-8000}"
RELOAD="${UVICORN_RELOAD:-false}"
WORKERS="${UVICORN_WORKERS:-2}"

if [ "$RELOAD" = "true" ]; then
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"

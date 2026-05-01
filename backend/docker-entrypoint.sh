#!/bin/sh
set -e

# Run DB migrations if alembic is present
if command -v alembic >/dev/null 2>&1 && [ -f ./alembic.ini ]; then
  echo "Running alembic migrations..."
  alembic upgrade head || echo "alembic upgrade failed; continuing"
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

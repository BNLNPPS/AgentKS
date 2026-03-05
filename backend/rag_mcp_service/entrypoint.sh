#!/bin/sh
set -e

echo "[entrypoint] Running RAG migrations..."
alembic upgrade head

echo "[entrypoint] Starting services..."
exec supervisord -c /app/supervisord.conf

#!/bin/sh
# Starts one GetDrove service inside its container.
# 1. Applies database migrations (skip with RUN_MIGRATIONS=false).
# 2. Starts Uvicorn on port 8000. ROOT_PATH tells FastAPI it sits behind the gateway at
#    /api/<service>, so Swagger UI works through Traefik.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Applying ${SERVICE} database migrations..."
  alembic -c /app/alembic.ini upgrade head
fi

exec uvicorn "${SERVICE}.infrastructure.main:app" \
  --host 0.0.0.0 \
  --port 8000 \
  --root-path "${ROOT_PATH:-/api/${SERVICE}}" \
  --proxy-headers \
  --forwarded-allow-ips "*"

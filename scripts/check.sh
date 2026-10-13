#!/usr/bin/env bash
# Runs every check that CI runs: the backend's format, lint, types, architecture rules and
# tests, then the frontend's (API types, lint, types, tests).
# Usage (from the repo root): bash scripts/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== Ruff format"
uv run ruff format --check .

echo "== Ruff lint"
uv run ruff check .

echo "== mypy (strict)"
uv run mypy

echo "== Architecture rules (import-linter)"
for service in services/*/; do
  echo "-- ${service}"
  (cd "$service" && uv run lint-imports)
done

echo "== Tests"
uv run pytest

echo "== Frontend (web/)"
if [ -d web/node_modules ]; then
  (cd web && npm run --silent check)
else
  echo "Skipped: run 'npm install' in web/ first."
fi

echo "All checks passed."

#!/usr/bin/env bash
# Runs every backend check that CI runs: format, lint, types, architecture rules and tests.
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

echo "All checks passed."

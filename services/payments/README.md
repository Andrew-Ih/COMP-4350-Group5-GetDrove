# Payments service

**Owner:** Chimdi

Pricing quotes, card setup, holds, captures and releases in Stripe test mode, driver earnings.

## Run locally

From the repo root:

```bash
uv sync
uv run --package payments uvicorn payments.infrastructure.main:app --reload --port 8004
```

Then open http://localhost:8004/health and the API docs at http://localhost:8004/docs.

## Test and check

```bash
uv run pytest services/payments
uv run mypy services/payments/src
cd services/payments && uv run lint-imports
```

## Database migrations

Tables live in the `payments` Postgres schema. With the database running and `PAYMENTS_DATABASE_URL` set:

```bash
cd services/payments
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/payments/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/payments/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/payments/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/payments/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/payments.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

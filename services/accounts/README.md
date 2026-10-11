# Accounts service

**Owner:** Fola

Sign-up with UofM email, verification, login and tokens, driver documents and approval, profiles, ratings, blocks and reports.

## Run locally

From the repo root:

```bash
uv sync
uv run --package accounts uvicorn accounts.infrastructure.main:app --reload --port 8001
```

Then open http://localhost:8001/health and the API docs at http://localhost:8001/docs.

## Test and check

```bash
uv run pytest services/accounts
uv run mypy services/accounts/src
cd services/accounts && uv run lint-imports
```

## Database migrations

Tables live in the `accounts` Postgres schema. With the database running and `ACCOUNTS_DATABASE_URL` set:

```bash
cd services/accounts
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/accounts/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/accounts/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/accounts/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/accounts/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/accounts.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

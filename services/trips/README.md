# Trips service

**Owner:** Andrew

Posting trips (one-off and recurring), search, seat requests, accept/decline, auto-accept, seats, trip execution and share links.

## Run locally

From the repo root:

```bash
uv sync
uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002
```

Then open http://localhost:8002/health and the API docs at http://localhost:8002/docs.

## Test and check

```bash
uv run pytest services/trips
uv run mypy services/trips/src
cd services/trips && uv run lint-imports
```

## Database migrations

Tables live in the `trips` Postgres schema. With the database running and `TRIPS_DATABASE_URL` set:

```bash
cd services/trips
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/trips/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/trips/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/trips/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/trips/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/trips.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

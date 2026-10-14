# Routing service

**Owner:** Rayan

Driving routes via OSRM, corridor matching, pickup points, detours, pickup ordering and ETAs.

## Run locally

From the repo root:

```bash
uv sync
uv run --package routing uvicorn routing.infrastructure.main:app --reload --port 8003
```

Then open http://localhost:8003/health and the API docs at http://localhost:8003/docs.

## Test and check

```bash
uv run pytest services/routing
uv run mypy services/routing/src
cd services/routing && uv run lint-imports
```

## Database migrations

Tables live in the `routing` Postgres schema. With the database running and `ROUTING_DATABASE_URL` set:

```bash
cd services/routing
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/routing/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/routing/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/routing/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/routing/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/routing.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

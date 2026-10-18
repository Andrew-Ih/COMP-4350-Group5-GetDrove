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

Computing a route needs OSRM running. Without it, `POST /internal/routes` answers 503. See [infra/osrm/README.md](../../infra/osrm/README.md) to prepare the map data once, then `docker compose --profile osrm up -d`.

## Test and check

```bash
uv run pytest services/routing
uv run mypy services/routing/src
cd services/routing && uv run lint-imports
```

The repository and API tests use a real PostgreSQL database with PostGIS (`docker compose up -d postgres`, then `uv run alembic upgrade head` in this folder). OSRM is always mocked in tests.

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

The OpenAPI spec is [contracts/openapi/routing.json](../../contracts/openapi/routing.json).

### Computing a trip's route (#24)

`POST /internal/routes` is called by Trips when a driver posts a trip. It's internal: only reachable inside Docker (`http://routing:8000/internal/routes`), never through the gateway.

1. Asks OSRM's car profile for the driving route between the origin and the destination.
2. Stores the full route in `routing.routes` as a PostGIS `LINESTRING` (SRID 4326, `[lng lat]` order), with its distance and duration. A GiST index on `path` is there for matching (#25, #26).
3. Returns the distance in meters and the duration in seconds, rounded to whole numbers.

Calling it again for the same trip replaces that trip's route. Errors:

| Status | Code | When |
|---|---|---|
| 422 | `invalid_input` | Bad coordinates, a point more than 500 m from a road on the map (so anywhere outside Winnipeg), or no road route between the points (OSRM's `NoSegment`, `NoRoute`) |
| 503 | `routing_engine_unavailable` | OSRM is down, errors, returns something unexpected, or takes longer than `ROUTING_OSRM_TIMEOUT_SECONDS` (default 2.5) |

Nothing is stored when a request fails.

## Events

_Published and consumed events, linking to `contracts/events/`._

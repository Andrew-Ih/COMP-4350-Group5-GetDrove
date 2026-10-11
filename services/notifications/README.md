# Notifications service

**Owner:** Daniel

Emails, in-app notifications, reminders and trip chat.

## Run locally

From the repo root:

```bash
uv sync
uv run --package notifications uvicorn notifications.infrastructure.main:app --reload --port 8005
```

Then open http://localhost:8005/health and the API docs at http://localhost:8005/docs.

## Test and check

```bash
uv run pytest services/notifications
uv run mypy services/notifications/src
cd services/notifications && uv run lint-imports
```

## Database migrations

Tables live in the `notifications` Postgres schema. With the database running and `NOTIFICATIONS_DATABASE_URL` set:

```bash
cd services/notifications
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/notifications/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/notifications/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/notifications/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/notifications/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/notifications.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

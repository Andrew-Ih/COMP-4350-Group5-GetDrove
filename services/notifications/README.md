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

Notifications needs PostgreSQL, Redis and an SMTP server; the defaults point at the ones Docker Compose starts on localhost (`docker compose up postgres redis mailpit`). Emails land in Mailpit at http://localhost:8025, and nothing reaches a real inbox. Settings are listed in `.env.example` under "Notifications email".

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

Consumed from the `events.accounts` stream as the `notifications` consumer group:

| Event | What Notifications does |
|---|---|
| [`UserRegistered`](../../contracts/events/user-registered.v1.json) | Emails the verification link ([#93](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/93)) |
| [`VerificationEmailRequested`](../../contracts/events/verification-email-requested.v1.json) | Emails the new verification link |

The link is `NOTIFICATIONS_WEB_BASE_URL` + `/verify?token=…`, the web app's verify page.

Each event is handled once: it's recorded in `processed_events` in the same transaction as the handler, so a repeat delivery or a restart skips it. A failed send is retried, and after 5 tries the event is parked in `failed_events`. If the service dies after the mail server accepted an email but before that commit, the email is sent once more on restart.

**`failed_events` holds personal data.** A parked event keeps its whole envelope: the student's email and a verification token that works until it expires (24 hours). Look at why it failed, then delete the row; don't copy envelopes into issues or chat.

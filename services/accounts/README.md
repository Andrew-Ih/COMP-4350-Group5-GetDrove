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

Accounts needs PostgreSQL (`ACCOUNTS_DATABASE_URL`) and Redis (`ACCOUNTS_REDIS_URL`); the defaults point at the ones Docker Compose starts on localhost (`docker compose up postgres redis`). Without Redis, endpoints still work, but the outbox relay logs a warning every second and events wait in the outbox until Redis is back.

## Test and check

```bash
uv run pytest services/accounts
uv run mypy services/accounts/src
cd services/accounts && uv run lint-imports
```

The tests in `tests/integration/` start a throwaway PostgreSQL with testcontainers, so **Docker must be running**; without it they're skipped with a message. They set up the `accounts` user and schema the way `infra/postgres/init` does and run the real migrations.

## Database migrations

Tables live in the `accounts` Postgres schema:

| Table | What it holds |
|---|---|
| `users` | One row per student. Email stored lowercase and unique; password as an Argon2id hash ([ADR 0020](../../docs/architecture/adr/0020-password-hashing.md)). |
| `verification_tokens` | Email verification links (SHA-256 hashes only). Used ones are kept so a used link (400) can be told apart from an expired one (410). |
| `refresh_tokens` | "Stay logged in" tokens (SHA-256 hashes only), with `replaced_by_id` to detect a stolen token being reused. |
| `outbox` | Events waiting to be sent to Redis ([libs/events](../../libs/events/README.md)). |

After changing `adapters/persistence/tables.py`, with the database running and `ACCOUNTS_DATABASE_URL` set:

```bash
cd services/accounts
uv run alembic revision --autogenerate -m "add phone number"
uv run alembic upgrade head
```

- **Read the generated file before committing it.** `migrations/env.py` limits autogenerate to the `accounts` schema so it doesn't try to drop PostGIS's or other services' tables, but check anyway.
- **Never edit a migration once it's merged**: it may already have run on teammates' machines and the live server. Add a new one instead.
- A new column on a table that has data needs to allow blanks or have a default, or the migration fails on existing rows.
- `test_tables_py_and_the_migrations_agree` fails if `tables.py` changes without a migration.

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

The contract is [`contracts/openapi/accounts.json`](../../contracts/openapi/accounts.json): sign up, verify, resend verification, log in, refresh, log out, `GET /me` and the JWKS endpoint. Implementations must match it exactly, including error `code` values.

## Events

| Event | Published when | Consumers |
|---|---|---|
| [`UserRegistered`](../../contracts/events/user-registered.v1.json) | A student signs up ([#4](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/4)) | Notifications sends the verification email ([#93](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/93)) |
| [`VerificationEmailRequested`](../../contracts/events/verification-email-requested.v1.json) | A student asks for a new link ([#5](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/5)); not for unknown or already-verified emails | Notifications sends the same email ([#93](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/93)) |

Events are saved to the `outbox` table in the same transaction as the change, then sent to the `events.accounts` Redis stream.

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

`TripPosted` is recorded transactionally and relayed to `events.trips`; see below.

## Posting one-off trips (#94)

`POST /` (gateway: `POST /api/trips/`) requires authentication and keeps the
existing API contract. Routing responses must contain the requested `tripId` and
non-negative integer metrics that fit PostgreSQL INTEGER columns. Malformed
responses, timeouts, and HTTP failures return `503 routing_unavailable`.
The local Routing URL defaults to `http://localhost:8003`, matching Routing's
documented development port; Docker supplies `TRIPS_ROUTING_URL` separately.

A successful request commits the Trip and a `TripPosted` outbox record in one
PostgreSQL transaction. Failures roll both back. The application depends on a
framework-free `TripEvents` port; the adapter uses the existing events library.
The lifespan runs its outbox relay against `TRIPS_REDIS_URL` (default
`redis://localhost:6379/0`). Redis outages leave events pending for retry and do
not undo committed trips.

`TripPosted` version 1 is published on `events.trips` with payload
`{"tripId": "<UUID>"}` and the standard event envelope/correlation ID. It contains
no home coordinates, address labels, or driver identity. Consumers must handle
redelivery idempotently. The producer payload is defined in `adapters/events.py`;
agree any additional fields with consumers before extending this contract.

### Database tests

Use a dedicated PostgreSQL test database with a `trips` schema owned by its test
user. Set `TRIPS_DATABASE_URL`, then run `uv run alembic upgrade head` from this
folder before running tests from the repository root. Tests commit to verify
visibility through another connection and clean up their own Trip/outbox rows.
Routing is mocked; these tests do not exercise a live Routing server or Redis.

### Cross-service consistency: team decision required

The PostgreSQL transaction cannot roll back a route already stored by Routing.
A database/outbox failure after Routing succeeds can leave an orphan route. A
Routing timeout is ambiguous: the remote write may finish after the client stops
waiting. Retrying the public POST creates a new Trip ID and can create duplicates
if the original PostgreSQL commit succeeded but its response was lost.

Recommended follow-up: agree a stable request idempotency key and a durable
compensation/reconciliation workflow with the Routing team. Failed route writes
need retryable cleanup (including retention of private route geometry); a single
best-effort delete is insufficient when cleanup itself fails. Routing's existing
same-Trip-ID replacement contract helps internal retries, but does not make the
public POST idempotent. The outbox makes Trip/event persistence atomic, not the
Routing write. No compensation API, automatic public-POST retry, pending-Trip
workflow, or Routing service change is introduced here.

The checked-in Routing compute handler is still a 501 contract stub (#23-#26).
A deployed Routing implementation is required for a live successful POST; the
Trips adapter maps its HTTP failures to the existing 503 response.

## Searching for trips (#97)

`GET /search?lat=&lng=&direction=&time=` (gateway: `GET /api/trips/search`) requires authentication and returns the trips that pass near the rider, soonest departure first.

1. **Candidates** (this service): scheduled trips in the rider's direction with a free seat that haven't left yet, excluding the rider's own. Going to campus, `time` is when the rider wants to arrive: trips arriving in the hour before it. Leaving campus, it's when they want to leave: trips departing in the hour after it. Both ends are included.
2. **Matching** (Routing, `POST /internal/matches`): which candidates the rider can walk to, with a pickup point on the route, the walking time, and how far the rider rides. No candidates means Routing isn't called.
3. **Cost** (Payments, `POST /internal/quotes`): the rider's share for how far they ride. Going to campus that's from the pickup to campus (Routing's `riderDistanceMeters`); leaving campus it's from campus to the drop-off (the trip's distance minus it). A price is optional: if Payments fails or is slow (2 s timeout), the trip is still shown with `cost: null`. Until the quote endpoint lands (#99), Payments answers 501, so every cost is null.

Each result is the trip as a rider sees it: the driver's own end (`origin` going to campus, `destination` leaving it) is null, so their home area is never shown. If Routing can't answer, the search fails with 503 `routing_unavailable`; an empty list is a normal result. The rider's location is only passed to Routing, never stored.

Settings: `TRIPS_PAYMENTS_URL` (default `http://localhost:8004`; Docker Compose sets `http://payments:8000`).

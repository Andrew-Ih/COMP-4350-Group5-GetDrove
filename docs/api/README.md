# API documentation

Where to find the documentation for every GetDrove API and event. The contracts in [`contracts/`](../../contracts/README.md) are the source of truth: they're generated from the services' code, so they always match what the services actually do as long as they're regenerated with each change.

## Services

Each service documents its own API in Swagger UI, where you can read every endpoint, its request and response shapes, its errors, and try it out.

| Service | What it does | Swagger UI (Docker Compose) | Swagger UI (one service with uv) | Contract |
|---|---|---|---|---|
| Accounts | Signup, email verification, login, sessions, the logged-in user, public keys for tokens | http://localhost/api/accounts/docs | http://localhost:8001/docs | [accounts.json](../../contracts/openapi/accounts.json) |
| Trips | Posting trips, my trips, trip detail, trip search | http://localhost/api/trips/docs | http://localhost:8002/docs | [trips.json](../../contracts/openapi/trips.json) |
| Routing | Driving routes, matching riders to trips, route lines for the map | http://localhost/api/routing/docs | http://localhost:8003/docs | [routing.json](../../contracts/openapi/routing.json) |
| Payments | Price quotes for a rider's share | http://localhost/api/payments/docs | http://localhost:8004/docs | [payments.json](../../contracts/openapi/payments.json) |
| Notifications | Sends emails when events arrive (no public endpoints besides health) | http://localhost/api/notifications/docs | http://localhost:8005/docs | [notifications.json](../../contracts/openapi/notifications.json) |

- **Docker Compose:** `docker compose up --build` from the repo root, then use the first column. See [Local Docker setup](../deployment/docker-setup.md).
- **One service with uv:** each service's README has the command, for example `uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002`.
- **Without running anything:** open a contract file in [Swagger Editor](https://editor.swagger.io) (File → Import file), or read it on GitHub.

Every path in a contract is relative to `/api/<service>`, so `GET /search` in `trips.json` is `GET /api/trips/search` through the gateway.

## Endpoints at a glance

🔒 means the endpoint needs `Authorization: Bearer <access token>` from Accounts.

| Service | Endpoint | What it does |
|---|---|---|
| Accounts | `POST /api/accounts/auth/signup` | Sign up |
| | `POST /api/accounts/auth/verify` | Verify an email address |
| | `POST /api/accounts/auth/resend-verification` | Send a new verification email |
| | `POST /api/accounts/auth/login` | Log in |
| | `POST /api/accounts/auth/refresh` | Get a new access token (refresh cookie) |
| | `POST /api/accounts/auth/logout` | Log out |
| | `GET /api/accounts/me` 🔒 | The logged-in user |
| | `GET /api/accounts/.well-known/jwks.json` | Public keys other services use to check access tokens |
| Trips | `POST /api/trips` 🔒 | Post a trip |
| | `GET /api/trips/mine` 🔒 | My upcoming trips |
| | `GET /api/trips/search` 🔒 | Find trips that pass near the rider |
| | `GET /api/trips/{tripId}` 🔒 | Trip detail |
| Routing | `GET /api/routing/trips/{tripId}/geometry` 🔒 | A trip's route for the map |
| | `POST /internal/routes` | Internal: compute and store a trip's driving route (called by Trips) |
| | `POST /internal/matches` | Internal: find which trips pass near a rider (called by Trips) |
| Payments | `POST /internal/quotes` | Internal: price a rider's share (called by Trips) |

Every service also has `GET /api/<service>/health`.

**Internal endpoints** (`/internal/...`) are for service-to-service calls only. The gateway never exposes them, so they show up in Swagger UI and the contracts but can't be reached from the browser or the live site.

This table is a summary. When it and a contract disagree, the contract is right.

## Events

Services also talk through events on Redis Streams. How publishing and consuming works (the outbox, retries, handling each event once) is in [libs/events](../../libs/events/README.md).

| Event | Published by | Consumed by | When | Schema |
|---|---|---|---|---|
| `UserRegistered` v1 | Accounts | Notifications | A student signs up (sends the verification email) | [user-registered.v1.json](../../contracts/events/user-registered.v1.json) |
| `VerificationEmailRequested` v1 | Accounts | Notifications | A student asks for a new verification link | [verification-email-requested.v1.json](../../contracts/events/verification-email-requested.v1.json) |

The schemas are generated from the event classes in [`libs/events/src/events/catalog/`](../../libs/events/src/events/catalog/), which also say which stream each event goes on.

## Shared rules

These apply to every API, so they're documented once:

- **Conventions** (camelCase JSON, UUIDs, UTC times, money in cents, status codes, privacy): [contracts/README.md](../../contracts/README.md#conventions-all-services)
- **Errors** (Problem Details with a stable `code` and `requestId`, and how errors are documented): [libs/common-web](../../libs/common-web/README.md)
- **Login and access tokens:** [ADR 0006](../architecture/adr/0006-gateway-and-authentication.md) and [ADR 0022](../architecture/adr/0022-login-sessions.md)

## Changing an API

1. Change the service's code and regenerate the contracts: `uv run python scripts/export_openapi.py`
2. Regenerate the frontend's types: `cd web && npm run api:generate` (they live in `web/src/shared/api/generated/`)
3. Commit both, and get the consumers to approve the PR. The full steps are in [contracts/README.md](../../contracts/README.md#how-to-write-a-contract).

CI checks that the frontend's types match the contracts (`npm run api:check`). To check the contracts match the code yourself, run `uv run python scripts/export_openapi.py --check`; CI will run it too once #178 is done.

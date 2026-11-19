# API documentation

Where to find the documentation for every GetDrove API and event. The contracts in [`contracts/`](../../contracts/README.md) are the source of truth: they're generated from the services' code, so they always match what the services actually do as long as they're regenerated with each change.

## Services

Each service documents its own API in Swagger UI, where you can read every endpoint, its request and response shapes, its errors, and try it out.

| Service | What it does | Swagger UI (Docker Compose) | Swagger UI (one service with uv) | Contract |
|---|---|---|---|---|
| Accounts | Signup, email verification, login, sessions, the logged-in user, public profiles, driver documents and vehicles, admin approval, public keys for tokens | http://localhost/api/accounts/docs | http://localhost:8001/docs | [accounts.json](../../contracts/openapi/accounts.json) |
| Trips | Posting one-off and recurring trips, trip search and detail, seat requests and decisions, auto-accept, cancellations, my trips | http://localhost/api/trips/docs | http://localhost:8002/docs | [trips.json](../../contracts/openapi/trips.json) |
| Routing | Driving routes, matching riders to trips, pickup points, detours, route lines for the map, address search | http://localhost/api/routing/docs | http://localhost:8003/docs | [routing.json](../../contracts/openapi/routing.json) |
| Payments | Price quotes, saved cards, holds on the rider's card | http://localhost/api/payments/docs | http://localhost:8004/docs | [payments.json](../../contracts/openapi/payments.json) |
| Notifications | The in-app bell and an email for each request and trip update, the verification email, ride reminders | http://localhost/api/notifications/docs | http://localhost:8005/docs | [notifications.json](../../contracts/openapi/notifications.json) |

- **Docker Compose:** `docker compose up --build` from the repo root, then use the first column. See [Local Docker setup](../deployment/docker-setup.md).
- **One service with uv:** each service's README has the command, for example `uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002`.
- **Without running anything:** open a contract file in [Swagger Editor](https://editor.swagger.io) (File → Import file), or read it on GitHub.

Every path in a contract is relative to `/api/<service>`, so `GET /search` in `trips.json` is `GET /api/trips/search` through the gateway.

## Endpoints at a glance

🔒 means the endpoint needs `Authorization: Bearer <access token>` from Accounts.

| Service | Endpoint | What it does |
|---|---|---|
| Accounts | `POST /api/accounts/auth/signup` | Sign up |
|  | `POST /api/accounts/auth/verify` | Verify email |
|  | `POST /api/accounts/auth/resend-verification` | Resend the verification email |
|  | `POST /api/accounts/auth/login` | Log in |
|  | `POST /api/accounts/auth/refresh` | Get a new access token |
|  | `POST /api/accounts/auth/logout` | Log out |
|  | `GET /api/accounts/me` 🔒 | The logged-in user |
|  | `GET /api/accounts/.well-known/jwks.json` | Public keys for checking access tokens |
|  | `GET /api/accounts/me/driver` 🔒 | My driver status |
|  | `PUT /api/accounts/me/driver/documents` 🔒 | Upload my licence and insurance |
|  | `GET /api/accounts/me/driver/documents/{kind}` 🔒 | Open one of my documents |
|  | `PUT /api/accounts/me/driver/vehicle` 🔒 | Save my vehicle |
|  | `GET /api/accounts/admin/drivers` 🔒 | Driver applications |
|  | `GET /api/accounts/admin/drivers/{userId}/documents/{kind}` 🔒 | Open a driver's document |
|  | `POST /api/accounts/admin/drivers/{userId}/approve` 🔒 | Approve a driver |
|  | `POST /api/accounts/admin/drivers/{userId}/reject` 🔒 | Reject a driver |
|  | `GET /api/accounts/users/{userId}/profile` 🔒 | A user's public profile |
|  | `GET /internal/users` | Internal: names, ratings and no-shows |
|  | `GET /internal/contacts` | Internal: names and emails |
| Trips | `POST /api/trips` 🔒 | Post a trip |
|  | `POST /api/trips/series` 🔒 | Post a recurring weekday trip |
|  | `GET /api/trips/mine` 🔒 | My trips as a driver |
|  | `GET /api/trips/requests/mine` 🔒 | My trips as a rider |
|  | `GET /api/trips/auto-accept` 🔒 | My auto-accept rules |
|  | `PUT /api/trips/auto-accept` 🔒 | Set my auto-accept rules |
|  | `GET /api/trips/search` 🔒 | Find trips that pass near the rider |
|  | `GET /api/trips/requests/{requestId}` 🔒 | One seat request |
|  | `POST /api/trips/requests/{requestId}/accept` 🔒 | Accept a request |
|  | `POST /api/trips/requests/{requestId}/decline` 🔒 | Decline a request |
|  | `POST /api/trips/requests/{requestId}/cancel` 🔒 | Cancel my request |
|  | `POST /api/trips/series/{seriesId}/cancel` 🔒 | Cancel a recurring series |
|  | `GET /api/trips/{tripId}` 🔒 | Trip detail |
|  | `POST /api/trips/{tripId}/cancel` 🔒 | Cancel a trip |
|  | `POST /api/trips/{tripId}/requests` 🔒 | Request a seat |
|  | `GET /api/trips/{tripId}/requests` 🔒 | Requests on my trip |
| Routing | `POST /internal/routes` | Internal: compute and store a trip's driving route |
|  | `POST /internal/matches` | Internal: find which trips pass near a rider |
|  | `POST /internal/pickup-points` | Internal: pickup points for a rider on a trip |
|  | `POST /internal/detours` | Internal: extra driving time for a new pickup |
|  | `GET /api/routing/trips/{tripId}/geometry` 🔒 | A trip's route for the map |
|  | `POST /api/routing/places` 🔒 | Find a place by its address |
| Payments | `POST /internal/quotes` | Internal: price a rider's share |
|  | `GET /internal/customers/{userId}/card` | Internal: does this rider have a card? |
|  | `POST /api/payments/setup-intent` 🔒 | Start adding a card |
|  | `GET /api/payments/methods` 🔒 | My saved cards |
| Notifications | `GET /api/notifications` 🔒 | My notifications |
|  | `POST /api/notifications/read-all` 🔒 | Mark all as read |
|  | `POST /api/notifications/{notificationId}/read` 🔒 | Mark one as read |

Every service also has `GET /api/<service>/health`.

**Internal endpoints** (`/internal/...`) are for service-to-service calls only. The gateway never exposes them, so they show up in Swagger UI and the contracts but can't be reached from the browser or the live site.

This table is a summary. When it and a contract disagree, the contract is right.

## Events

Services also talk through events on Redis Streams. How publishing and consuming works (the outbox, retries, handling each event once) is in [libs/events](../../libs/events/README.md).

| Event | Published by | Consumed by | When | Schema |
|---|---|---|---|---|
| `UserRegistered` v1 | Accounts | Notifications (the verification email) | A student signs up | [user-registered.v1.json](../../contracts/events/user-registered.v1.json) |
| `VerificationEmailRequested` v1 | Accounts | Notifications | A student asks for a new verification link | [verification-email-requested.v1.json](../../contracts/events/verification-email-requested.v1.json) |
| `DriverApproved` v1 | Accounts | Trips (the driver may post), Notifications | An admin approves a driver | [driver-approved.v1.json](../../contracts/events/driver-approved.v1.json) |
| `DriverRejected` v1 | Accounts | Trips, Notifications | An admin rejects a driver, with a reason | [driver-rejected.v1.json](../../contracts/events/driver-rejected.v1.json) |
| `TripPosted` v1 | Trips | None yet | A driver posts a trip | [trip-posted.v1.json](../../contracts/events/trip-posted.v1.json) |
| `SeatRequested` v1 | Trips | Notifications (the driver is told) | A rider asks for a seat | [seat-requested.v1.json](../../contracts/events/seat-requested.v1.json) |
| `RequestAccepted` v1 | Trips | Payments (places the hold), Routing (detour plan cache), Notifications (rider told, reminder scheduled) | The driver, or auto-accept, accepts a request | [request-accepted.v1.json](../../contracts/events/request-accepted.v1.json) |
| `RequestDeclined` v1 | Trips | Payments, Routing, Notifications | The driver declines a request | [request-declined.v1.json](../../contracts/events/request-declined.v1.json) |
| `RequestCancelled` v1 | Trips | Payments (releases the hold), Routing, Notifications | The rider cancels their request | [request-cancelled.v1.json](../../contracts/events/request-cancelled.v1.json) |
| `TripCancelled` v1 | Trips | Payments (releases the holds), Routing, Notifications | The driver cancels a trip or a series | [trip-cancelled.v1.json](../../contracts/events/trip-cancelled.v1.json) |
| `DriverLateCancellation` v1 | Trips | None yet (Accounts, Sprint 3, #134) | A trip is cancelled less than an hour before it leaves | [driver-late-cancellation.v1.json](../../contracts/events/driver-late-cancellation.v1.json) |
| `PaymentHeld` v1 | Payments | None yet | The rider's share is held on their card | [payment-held.v1.json](../../contracts/events/payment-held.v1.json) |
| `PaymentReleased` v1 | Payments | None yet | A hold is cancelled because the ride won't happen | [payment-released.v1.json](../../contracts/events/payment-released.v1.json) |
| `PaymentFailed` v1 | Payments | Trips (frees the seat), Notifications (the rider is told) | A hold can't be placed (no card, declined, needs authentication) | [payment-failed.v1.json](../../contracts/events/payment-failed.v1.json) |

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

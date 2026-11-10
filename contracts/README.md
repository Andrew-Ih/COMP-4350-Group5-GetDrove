# API contracts

The agreed interfaces between services and the frontend (issue #108). A contract is written **before** the code behind it, so the frontend and other services can build against it straight away.

| Folder | What's in it |
|---|---|
| `openapi/<service>.json` | Each service's OpenAPI spec, generated from its code. Paths are relative to `/api/<service>` (the spec's `servers` entry). |
| `events/<event>.v<N>.json` | JSON Schema of each shared event, generated from `libs/events/src/events/catalog/`. |

You can also browse each service's contract in Swagger UI: `http://localhost/api/<service>/docs` with Docker Compose running, or `http://localhost:<port>/docs` when running one service with uv.

## How to write a contract

1. In your service, add the Pydantic request/response models to `adapters/api/schemas.py`, with `examples`, and the routes to a router in `adapters/api/`. Handlers return **501 Not Implemented** until the real code is written. Trips (`services/trips/src/trips/adapters/api/`) is the reference example.
2. Document every error the endpoint can return with `responses={...}` and its `code`.
3. Regenerate the specs and commit them with your change:
   ```bash
   uv run python scripts/export_openapi.py
   ```
4. Open a PR. **The consumers of the contract approve it** before anyone builds against it (for example, the frontend approves public endpoints; Trips approves Routing's internal endpoints).
5. Changing a contract later works the same way: change the code, regenerate, and get the consumers' approval. Never rename or remove a field or error `code` without telling the team.

## Conventions (all services)

| Topic | Rule |
|---|---|
| URLs | Public: `/api/<service>/...` through the gateway, plural nouns (`/api/trips`, `/api/trips/{id}/requests`). Service-to-service: `/internal/...`, never exposed by the gateway. |
| JSON fields | **camelCase** (Pydantic models use a camelCase alias generator) |
| IDs | UUIDs |
| Times | ISO 8601 **with a timezone**, sent in UTC: `2026-10-20T13:10:00Z` |
| Money | Integer **cents** plus `currency` (`"CAD"`): `{"amountCents": 420, "currency": "CAD"}` |
| Distances and durations | Integer `...Meters` and `...Seconds` |
| Places | `{"label": "Osborne St & River Ave", "lat": 49.881, "lng": -97.144}` |
| Auth | `Authorization: Bearer <access token>` from Accounts; missing or invalid token gives 401, not allowed gives 403 |
| Status codes | 200 read · 201 created · 204 no content · 401 · 403 · 404 · 409 conflict · 422 invalid input · 503 a dependency is down |
| Errors | Problem Details (RFC 9457, `application/problem+json`) with a stable `code` and the `requestId`; 422s list the invalid fields in `errors`. See [libs/common-web](../libs/common-web/README.md). |
| Empty results | An empty list with 200, not 404 |
| Lists that can grow large | `?limit=&cursor=` pagination (none needed in Sprint 1) |
| Privacy | Never return a user's home address or exact location to another user; drivers' and riders' private ends of a trip are `null` for others |
| Events | The envelope from [libs/events](../libs/events/README.md); payloads carry IDs and only the data consumers need |

## Sprint 1 contracts

| Contract | Service | Consumers | Status |
|---|---|---|---|
| Post trip, my trips, trip detail, search | Trips | Frontend | Written |
| Signup, verify, resend, login, refresh, logout, `GET /me`, JWKS | Accounts | Frontend, all services (JWKS) | Written |
| `UserRegistered` event (`libs/events/src/events/catalog/`) | Accounts | Notifications | Written |
| `VerificationEmailRequested` event (`libs/events/src/events/catalog/`) | Accounts | Notifications | Written |
| Compute route, find matches, route geometry | Routing | Trips, frontend (geometry) | Written |
| Price quote (internal) | Payments | Trips | Written |

## Sprint 2 contracts (#262)

Endpoints return 501 until the task in brackets implements them.

| Contract | Service | Consumers | Status |
|---|---|---|---|
| Recurring trips (#17), cancel a trip or series (#132, #18), trip detail with pickup points and price (#140), seat requests: request, accept, decline, cancel, one request, the driver's list (#137–#139), rider's trips `GET /requests/mine` (#130), past trips `?when=past`, auto-accept rules (#42) | Trips | Frontend | Written |
| Driver status, documents and vehicle (#9, #10, #125), admin approval (#127), public profile (#143) | Accounts | Frontend | Written |
| Internal user lookups: `/internal/users` (no email) and `/internal/contacts` (email) (#143, #146) | Accounts | Trips, Notifications | Written |
| Pickup points (#29, #30), detours (#36, #38), `driverId` and `direction` on `/internal/routes` (#135) | Routing | Trips | Written |
| Card setup and saved cards (#151), internal "has a card" check | Payments | Frontend, Trips | Written |
| Notifications list, mark read, mark all read (#145) | Notifications | Frontend | Written |
| `SeatRequested`, `RequestAccepted`, `RequestDeclined`, `RequestCancelled`, `TripCancelled`, `DriverLateCancellation` | Trips | Payments, Notifications, Routing, Accounts | Written |
| `DriverApproved`, `DriverRejected` | Accounts | Trips, Notifications | Written |
| `PaymentHeld`, `PaymentFailed`, `PaymentReleased` | Payments | Trips, Notifications | Written |

Changes to Sprint 1 contracts: `Trip` gains `seriesId`; `GET /api/trips/{tripId}` returns a
`TripDetail` instead of a `Trip`; `GET /api/trips/mine` only takes `role=driver` (a rider's
trips are `GET /api/trips/requests/mine`) and gains `when`; `POST /api/trips` can return
`403 driver_not_approved`; route geometry hides the driver's end from everyone but the driver.

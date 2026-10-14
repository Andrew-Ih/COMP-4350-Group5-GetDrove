# common-web

Shared HTTP behaviour for every GetDrove service (issue #103): consistent error responses, request IDs and logging. Each service turns it on with one line:

```python
from common_web.app import install

def create_app() -> FastAPI:
    app = FastAPI(...)
    install(app, service="trips")
    ...
```

## Errors

Every error from every service is a **Problem Details** response (RFC 9457), `application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "No seats left",
  "status": 409,
  "detail": "No seats left on this trip",
  "instance": "/api/trips/7f3c…/requests",
  "code": "no_seats_left",
  "requestId": "b1e2…"
}
```

- `code` is a short, stable name the frontend can check (don't match on `detail` text).
- `requestId` matches the `X-Request-ID` response header; quote it when reporting a bug.
- Validation errors (422) add `errors: [{"field": "seatsTotal", "message": "…"}]`, using the JSON (camelCase) field names.
- Unexpected errors (500) never include internal details; those go to the logs only.

**Raising errors.** Domain and application code raise plain exceptions from `common_web` (no FastAPI import needed). Subclass the closest base for each case in your service:

```python
from common_web import ConflictError

class NoSeatsLeftError(ConflictError):
    code = "no_seats_left"
    title = "No seats left"

raise NoSeatsLeftError("No seats left on this trip")
```

| Base | Status | Default `code` |
|---|---|---|
| `InvalidInputError(detail, [InvalidField(field, message)])` | 422 | `invalid_input` |
| `UnauthorizedError` | 401 | `unauthorized` |
| `ForbiddenError` | 403 | `forbidden` |
| `NotFoundError` | 404 | `not_found` |
| `ConflictError` | 409 | `conflict` |
| `DomainError` (base) | 400 | `bad_request` |

FastAPI's own errors (unknown route, wrong method, invalid request body) come out in the same format.

## Request IDs

- Each request uses the incoming `X-Request-ID` header if it looks like an ID, or gets a new one.
- The ID is returned in the `X-Request-ID` response header and added to every log line for that request.
- `common_web.current_request_id()` returns it. Send it as `X-Request-ID` when calling another service, and use it as `correlation_id` when publishing events, so one user action can be followed across services.

## Logging

Built on Python's standard `logging` (ADR 0019), so logs from Uvicorn, SQLAlchemy and our libraries come out in the same format.

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Trip posted", extra={"trip_id": str(trip.id), "seats": 3})
```

| Setting | Values | Default |
|---|---|---|
| `LOG_FORMAT` | `text` (readable, local) or `json` (one JSON object per line, server) | `text` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

Every line includes the service name and request ID, and the user ID once `common_web.set_user_id()` has been called (common-security does this after checking the token). Each request is logged once with method, path, status and duration in milliseconds; `/health` is skipped.

**Never log personal data:** no emails, names, addresses, locations or tokens. Log IDs instead.

# ADR 0019: Python's standard logging instead of structlog

- **Status:** Accepted
- **Date:** 2026-10-12
- **Amends:** [ADR 0017](0017-python-fastapi-backend.md) (the "Logging" row)

## Context

ADR 0017 chose structlog for structured JSON logs with correlation IDs. While building the shared web library (`libs/common-web`, issue #103) we looked at what logging actually needs to do:

- Every log line, from our code and from the libraries we use (Uvicorn, SQLAlchemy, our `events` library), should come out in one format with the service name, request ID and user ID.
- Lines should be JSON on the server and readable locally.
- Teammates should be able to log without learning anything new.

Uvicorn, SQLAlchemy, redis-py and our own libraries already log through Python's standard `logging` module.

## Options considered

- **structlog (ADR 0017):** a nicer API for adding fields (`log.info("trip_posted", trip_id=…)`) and request context built in. But it's an extra dependency, and making the libraries' standard-logging output match its format needs an extra adapter set up.
- **Standard `logging` with a small JSON formatter:** no new dependency; one setup covers our code and every library; everyone already knows the API. Adding fields is slightly clunkier (`extra={"trip_id": …}`), and we write the JSON formatter and request-ID injection ourselves (about 100 lines in `common-web`).

## Decision

Use Python's **standard `logging`**, configured once by `common_web` (`install(app, service=…)`):

- A JSON formatter (`LOG_FORMAT=json`, used on the server) and a readable text formatter (`LOG_FORMAT=text`, the local default).
- A log record factory adds `service`, `requestId` and `userId` to every record, whichever library created it.
- Extra fields are passed with `extra={...}`. Personal data (emails, names, addresses, locations, tokens) is never logged; IDs are.

## Consequences

**Positive**

- One less dependency, and one logging mechanism for our code and every library.
- Nothing new for teammates to learn.

**Negative / trade-offs**

- Adding fields is a little more verbose than with structlog.
- We maintain a small formatter ourselves; it's covered by tests in `libs/common-web`.

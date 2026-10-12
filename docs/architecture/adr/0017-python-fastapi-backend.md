# ADR 0017: Python 3.13 + FastAPI for all backend services

- **Status:** Accepted; realtime approach amended by [ADR 0018](0018-live-tracking-as-stretch-goal.md), logging by [ADR 0019](0019-standard-library-logging.md)
- **Date:** 2026-10-10
- **Supersedes:** [ADR 0003](0003-backend-framework.md) (backend framework), [ADR 0004](0004-build-tool.md) (build tool), and the backend tools in [ADR 0013](0013-testing.md)

## Context

ADR 0003 chose Java 21 + Spring Boot 3 for the five backend services. On reflection, the team prefers Python: it is faster to write, more of the team wants to use it, and FastAPI generates OpenAPI documentation with no extra setup, which the course requires from Sprint 1. Python supports everything the design needs (PostGIS, Stripe, Redis Streams, WebSockets, background jobs).

The main thing Java gave us for free was compile-time checking across services and enforced layer boundaries. This ADR replaces both with tooling, so Clean Architecture and contract safety are still enforced in CI.

## Options considered

- **Framework:** FastAPI (async, Pydantic validation, automatic OpenAPI, built-in WebSockets) · Django + DRF (batteries included, heavier, ORM-centric) · Flask (minimal, assemble everything).
- **Dependency and monorepo tool:** uv (fast, lockfile, workspaces) · Poetry (mature, workspaces need plugins) · pip + requirements.txt (no lockfile or workspaces).
- **Database layer:** SQLAlchemy 2 + Alembic (separate DB models from domain classes) · SQLModel (one class for both, weaker layering).
- **Type checking:** mypy strict in CI · mypy basic · none.

## Decision

All five services use **Python 3.13** and **FastAPI**, with:

| Concern | Choice |
|---|---|
| Web framework / server | FastAPI, served by Uvicorn |
| Validation and settings | Pydantic v2, pydantic-settings (configuration from environment variables) |
| Dependencies and monorepo | **uv** workspace: `libs/*` and `services/*` are workspace members with one lockfile (`uv.lock`) |
| Database | **SQLAlchemy 2** (async, asyncpg driver), **GeoAlchemy2** for PostGIS, **Alembic** for migrations; still one schema and one DB user per service |
| Messaging | redis-py (asyncio) for Redis Streams, behind the event library in `libs/events` |
| HTTP between services | httpx (async) with timeouts |
| Authentication (ADR 0006) | Accounts signs RS256 JWTs (PyJWT); each service validates them with Accounts' JWKS through a shared FastAPI dependency in `libs/common-security` |
| Realtime | FastAPI's built-in WebSockets with a small JSON message protocol (`subscribe`, `location`, `chat`, `notification`); token checked on connect, membership checked on subscribe |
| Scheduled jobs | Background tasks in the service's lifespan (asyncio), using `SELECT … FOR UPDATE SKIP LOCKED` for reminders and holds |
| Payments | Official `stripe` Python SDK |
| Logging | structlog (JSON logs with correlation IDs) |
| Formatting and linting | **Ruff** (format + lint) |
| Type checking | **mypy --strict**, required to pass in CI |
| Layer enforcement | **import-linter** contracts (domain → application → adapters → infrastructure), run in CI |
| Testing | pytest, pytest-asyncio, coverage.py (pytest-cov), testcontainers-python (PostGIS, Redis), respx (HTTP mocks), stripe-mock, Hypothesis where useful |
| Images | `python:3.13-slim` base, dependencies installed with uv, non-root user |

## Consequences

**Positive**

- Faster to write, and OpenAPI docs and interactive Swagger UI come free with FastAPI.
- Lighter containers than the JVM (roughly 80–150 MB of RAM per service), leaving more headroom on the 8 GB VM.
- uv workspaces keep the monorepo's shared libraries simple, with one lockfile for the backend.
- Async I/O suits services that mostly wait on the database, Redis, OSRM, and Stripe.

**Negative / trade-offs**

- Type safety and layering depend on tooling and discipline: mypy strict and import-linter must stay green in CI, and PRs that disable checks need a reason.
- Less built in than Spring (security, WebSockets, scheduling): we write small shared helpers in `libs/` for auth, errors, and events.
- Async code needs care: no blocking calls (use async drivers and clients), and tests use pytest-asyncio.
- CPU-heavy work in Python is slower than Java; the heaviest routing work runs in OSRM, so this matters little.

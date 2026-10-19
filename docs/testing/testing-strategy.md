# Testing strategy

How GetDrove is tested: the tools, what each kind of test checks, how we replace the parts we don't want in a test, and how to run everything. The tool choices are in [ADR 0013](../architecture/adr/0013-testing.md) (frontend and contracts) and [ADR 0017](../architecture/adr/0017-python-fastapi-backend.md) (backend).

## Tools

| Area | Tool | Used for |
|---|---|---|
| Backend tests | **pytest** with **pytest-asyncio** | Every backend test. Async tests run without decorators (`asyncio_mode = "auto"`). |
| Backend API tests | **httpx** (`ASGITransport`) | Calling a service's real FastAPI app in memory, without starting a server |
| Real databases in tests | **testcontainers** | A throwaway PostgreSQL + PostGIS, Redis or Mailpit in Docker for each test run |
| Backend coverage | **coverage.py** (pytest-cov) | Line and branch coverage of `libs/` and `services/` |
| Backend static checks | **Ruff** (format and lint), **mypy** (strict), **import-linter** | Style, bugs caught without running code, and each service's architecture rules |
| Frontend tests | **Vitest** with **React Testing Library** and **user-event** | Logic, hooks and components, in a simulated browser (jsdom) |
| Frontend API mocking | **MSW** and fetch spies | A fake API for the screens (see below) |
| Frontend coverage | **Vitest coverage** (`@vitest/coverage-v8`) | Line, branch and function coverage of `web/src/` |
| Frontend static checks | **ESLint** (with folder rules), **TypeScript** | Style, imports between features, type errors |
| Contracts | **openapi-typescript** (`npm run api:check`) and contract tests | Frontend types match the contracts; each service's routes match its contract |

## Kinds of tests

### Backend

Each service follows the same layers (domain, application, adapters, infrastructure; see [Monorepo structure](../architecture/monorepo.md)), and the tests follow them too. Accounts and Notifications have the full set and are the examples to copy.

| Kind | Where | What it checks | Database? |
|---|---|---|---|
| **Domain unit tests** | `tests/domain/` | Rules on plain objects: a valid UofM email, when a token expires, what a refresh token rotation does | No |
| **Use-case tests** | `tests/application/` | One use case end to end (sign up, log in, send a verification email) with in-memory fakes for the database, clock and password hasher | No |
| **Adapter tests** | `tests/adapters/` | One adapter on its own: the password hasher, access tokens, the SMTP sender | No |
| **API and contract tests** | `tests/test_contract.py`, `tests/test_errors.py`, `tests/test_health.py` | Routes exist, reject invalid input with the right `code`, need a login where they should, and every error is documented with its own example | No |
| **Integration tests** | `tests/integration/` | The real thing through the API or repository: real PostgreSQL with the real Alembic migrations, real Redis Streams, real email to Mailpit. Includes the full signup → event → verification email flow. | Yes (testcontainers) |
| **Library tests** | `libs/*/tests/` | Shared code: error responses and logging (common-web), token checking and JWKS (common-security), the outbox and stream consumer (events, against real PostgreSQL and Redis) | Some |

**Architecture rules** run with import-linter (`uv run lint-imports` in each service), so, for example, the domain layer can't import FastAPI or SQLAlchemy. CI fails if a rule is broken.

### Frontend

Code is grouped by feature (`web/src/features/<feature>/`), and each feature's tests sit next to the code.

| Kind | Where | What it checks |
|---|---|---|
| **Model tests** | `features/*/model/*.test.ts` | Plain functions: form validation, building a request, sorting results, formatting money and times, the overlap warning |
| **Hook tests** | `features/*/hooks/*.test.ts` | Hooks with timers or state, for example the resend cooldown |
| **Component tests** | `features/*/ui/*.test.tsx`, `shared/ui/*.test.tsx` | A screen or component as a user sees it: render it, type and click with user-event, check what appears. Covers loading, empty and error states and the server's error codes. |
| **API layer tests** | `shared/api/*.test.ts` | Problem Details parsing, and the login session (refresh, single refresh across tabs, logout) |
| **Mock API tests** | `shared/mocks/*.test.ts` | The mock API's answers match the types generated from the contracts, so the demo data can't drift from the real API |

Tests find elements the way a user does (by label, role or text), not by CSS classes, so they keep passing when the styling changes.

## Mocking: what we replace and how

The rule: **replace what's slow, outside our control or not built yet; keep everything else real.**

| What | In unit and component tests | In integration tests |
|---|---|---|
| Database | In-memory fakes of the repositories and unit of work (`accounts/testing.py`) | Real PostgreSQL + PostGIS (testcontainers), with the real migrations |
| Redis Streams | `FakeEvents`, which records the published events | Real Redis (testcontainers) |
| Email | `FakeEmailSender`, which records the emails | Real SMTP into Mailpit (testcontainers), then the email is read back through Mailpit's API |
| Time | `FakeClock` with a fixed "now" | Real time |
| Logging in | `common_security.testing.TestAuth`: a throwaway signing key and tokens, so a service can test protected endpoints without running Accounts | The same |
| Other services | Not called yet in Sprint 1. When Trips calls Routing and Payments, those calls go through a port with a fake in tests | (planned) |
| The backend, from the frontend | `mockFetch` (answers in order) and `mockApi` (answers by path) in `shared/testing/render.tsx` | — |
| The backend, in the browser | MSW (`shared/mocks/`): `npm run dev:mock` runs the whole frontend against demo data, so screens can be built before their endpoints exist | — |

Fakes live in each service's `testing` module (`accounts/testing.py`, `notifications/testing.py`), never in the running code paths, and they implement the same ports as the real adapters. If a fake and the real adapter could disagree, an integration test covers the real one.

Integration tests need Docker. Without it they're **skipped with a message**, not failed, so you can still run the fast tests anywhere. CI always has Docker, so every pull request runs them.

## Contracts

The API contracts (`contracts/`) are generated from the services' code, and the frontend's types are generated from the contracts. Three checks keep them together:

- **Contract tests** in each service (`test_contract.py`) check that the routes, inputs and documented errors are what the frontend expects.
- **`npm run api:check`** in CI fails if the frontend's generated types are out of date with the contracts.
- **Mock API tests** check that the frontend's demo data has the same shape as the contracts.

`uv run python scripts/export_openapi.py --check` checks that the contract files match the code. CI will run it too once #178 is done. See [API documentation](../api/README.md).

## Running the tests

```bash
# Everything CI runs (backend and frontend)
bash scripts/check.sh

# Backend
uv run pytest                                  # all backend tests (start Docker for integration tests)
uv run pytest services/accounts                # one service
uv run pytest --cov --cov-report=html          # with coverage; open htmlcov/index.html

# Frontend (in web/)
npm test                                       # all frontend tests
npm run test:watch                             # rerun on save
npm run test:coverage                          # with coverage; open web/coverage/index.html
```

In CI, every pull request into `develop` or `main` runs both with coverage. The totals appear on the run's summary page, and the full HTML reports are downloadable from the run as `backend-coverage-report` and `frontend-coverage-report`.

## What a pull request needs

- New domain rules and use cases come with unit tests.
- New endpoints come with contract tests, including each error `code`.
- Anything that touches the database, Redis or email gets an integration test.
- New screens come with component tests for the main path and the loading, empty and error states.
- A bug fix comes with a test that fails without the fix.

## Not used yet

These are planned in the ADRs but not set up yet. They're listed so nobody assumes they exist:

| Tool | For | When |
|---|---|---|
| Playwright | End-to-end tests in a real browser against the full stack | When the main rider and driver flows work end to end |
| respx | Mocking HTTP calls between services | When Trips starts calling Routing and Payments |
| stripe-mock | Payments tests | With the payments work |
| Hypothesis | Property-based tests (for example, pricing and route corridors) | Where a rule has many edge cases |
| JMeter, CodeQL, Trivy | Load testing and security scanning | Sprint 3 (#191, #188) |

## Coverage

Coverage is measured on every pull request. To see the current numbers:

- **On GitHub:** open the CI run for any pull request. The summary page shows the backend and frontend totals, and the full reports can be downloaded as `backend-coverage-report` and `frontend-coverage-report`.
- **Locally:** `uv run pytest --cov --cov-report=html` and `cd web && npm run test:coverage`, then open `htmlcov/index.html` and `web/coverage/index.html`.

Coverage counts the code that runs during tests. It leaves out the tests themselves, migrations, test helpers, the frontend's mock API and the types generated from the contracts, since counting those would make the numbers look better than they are.

The Sprint 1 coverage report, with what's under-tested and why, is added at the end of the sprint (#112).

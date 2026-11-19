# Testing strategy

How GetDrove is tested: the tools, what each kind of test checks, how we replace the parts we don't want in a test, and how to run everything. The tool choices are in [ADR 0013](../architecture/adr/0013-testing.md) (frontend and contracts) and [ADR 0017](../architecture/adr/0017-python-fastapi-backend.md) (backend).

When the tests run, how long they take and what happens when they fail is in [Regression testing](regression.md).

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
| Smoke test after deploy | **Playwright** (`e2e/`) | A demo rider logs in and searches on the live site after every deploy (#177) |
| Payments against Stripe | **stripe-mock** (testcontainers), and opt-in tests against our Stripe sandbox | The Stripe calls Payments makes, without real keys in CI |

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

In CI, every pull request into a feature branch, `develop` or `main` runs both with coverage. The totals appear on the run's summary page, and the full HTML reports are downloadable from the run as `backend-coverage-report` and `frontend-coverage-report`.

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
| Playwright, beyond the smoke test | End-to-end tests of the main rider and driver flows in CI, against the full stack | Final release (see the coverage gaps) |
| respx | Mocking HTTP calls between services | When Trips starts calling Routing and Payments |
| Hypothesis | Property-based tests (for example, pricing and route corridors) | Where a rule has many edge cases |
| JMeter, CodeQL, Trivy | Load testing and security scanning | Sprint 3 (#191, #188) |

## Coverage

Coverage is measured on every pull request. To see the current numbers:

- **On GitHub:** open the CI run for any pull request. The summary page shows the backend and frontend totals, and the full reports can be downloaded as `backend-coverage-report` and `frontend-coverage-report` (kept for 14 days).
- **Locally:** `uv run pytest --cov --cov-report=html` and `cd web && npm run test:coverage`, then open `htmlcov/index.html` and `web/coverage/index.html`.

Coverage counts the code that runs during tests. It leaves out the tests themselves, migrations, test helpers, the frontend's mock API and the types generated from the contracts, since counting those would make the numbers look better than they are.

### Sprint 2 report

Measured on `develop` at the end of Sprint 2 (commit `d586b8b`, 18 November 2026) by the [Delivery run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44354061351), with every test running: **1,838 backend tests** (4 opt-in Stripe sandbox tests skipped; see [regression testing](regression.md#1-which-tests-are-in-the-regression-suite)) and **482 frontend tests**. All passed. The full per-file reports from that run are kept as PDFs: [backend](backend-coverage-sprint2.pdf), [frontend](frontend-coverage-sprint2.pdf).

**Backend: 97%** (statements and branches together; 98.1% of statements). Sprint 1: 98%, with 2.6 times less code.

| Package | Statements | Statements covered | Branches partly covered | Sprint 1 |
|---|---|---|---|---|
| Accounts | 1,409 | 99.7% | 5 of 122 | 99.9% of 701 |
| Trips | 2,117 | 99.1% | 21 of 284 | 99.1% of 527 |
| Notifications | 895 | 98.3% | 3 of 66 | 100% of 165 |
| Payments | 812 | 96.1% | 23 of 160 | 97.9% of 95 |
| Routing | 908 | 96.0% | 1 of 112 | 97.8% of 504 |
| `libs/common-security` | 147 | 98.6% | 2 of 18 | 98.6% |
| `libs/common-web` | 290 | 97.6% | 5 of 66 | 97.8% |
| `libs/events` | 367 | 96.5% | 5 of 42 | 94.9% |
| **Total** | **6,945** | **98.1%** | **65 of 870** | 98.5% of 2,686 |

**Frontend: 86.5%** of lines (86.2% of statements, 86.9% of branches, 85.2% of functions). Sprint 1: 79%.

| Area | Lines covered |
|---|---|
| Feature logic (`features/*/model`, `api`, `hooks`) | 85–100% |
| Screens (`features/*/ui`) | 90–98%, except payments (63%, below) |
| Shared API and login session (`shared/api`) | 100% (75% of branches in `session.ts`) |
| Shared components (`shared/ui`) | 86% |
| Map (`shared/map`) | 29% |
| Next.js pages (`app/`) | 0% (one page, `app/page.tsx`, at 100%) |

### What the numbers mean

**Where we're strong.** The rules that matter most are the best covered: seat requests, accepting and declining, auto-accept, cancellations and recurring trips in Trips (99%), and driver approval and documents in Accounts (99.7%). Each use case has unit tests with fakes, and each database, Redis and SMTP adapter has integration tests against the real thing. The seat-overselling risk has its own concurrency tests on real PostgreSQL (#50). On the frontend, the new Sprint 2 screens (posting a trip and a series, trip requests, auto-accept, driver approval, notifications, my trips) are 90–98% covered, which is why the total went from 79% to 86.5%.

**Where we're weak, and why.** The low numbers are in three places, and they share a cause: code that only runs when the real app starts, or in a real browser.

- **Startup and wiring.** Routing's startup (`routing/infrastructure/main.py`, 53%), the Routing event handler that frees cached detour plans when a request changes (`routing/adapters/events/handlers.py`, 54%), and Notifications' database-backed bell (`notifications/adapters/api/dependencies.py`, 64%). The tests give each app its dependencies directly, so the code that builds them at startup never runs in a test. The parts they connect are tested on their own.
- **Payments' hold edge cases** (`payments/application/holds.py` 89%, `payments/adapters/persistence/holds.py` 87%, 23 partly covered branches). The main paths (place a hold, release it three ways, a declined card) are tested; some rare ones aren't (below).
- **The browser.** Next.js pages, the map and Stripe's card field (below).

Dropping from 98% to 97% on the backend is from Payments and Routing growing faster than their tests; the other packages held steady or went up.

### Gaps

The gaps we know about, why they exist, and what we'll do. Each one points at the code.

**1. Pages, the map and the Stripe card field are never tested in a browser.** The Next.js pages (`web/src/app/`, 0%), the map (`shared/map/MapView.client.tsx`, 0%: MapLibre needs WebGL, which jsdom doesn't have) and Stripe's card field (`features/payments/ui/StripeCardField.tsx`, 7%: Stripe's iframe only loads in a real browser) are what a student actually sees, but our component tests run in jsdom. The only browser test is the post-deploy smoke test (#177), which logs in and searches. So a broken redirect between pages, a map that doesn't draw, or a card form that doesn't load would only be caught by hand. **Plan: before the final release**, Playwright tests in CI against the Docker stack for the main flow: a rider requests a seat with a saved test card, the driver accepts, and the rider sees the hold and the notification (#435).

**2. Stripe itself is only tested by hand.** In CI, Payments runs against fakes and `stripe-mock`, which checks our requests' shape but not Stripe's behaviour. The tests against our real Stripe sandbox (a hold, its three kinds of release, a declined card) are opt-in and skipped in CI, because they need a test key. Some hold paths aren't tested at all (`payments/application/holds.py` lines 69, 101, 120, 148–151, 188–195): a card that needs 3-D Secure when the hold is placed (Stripe's `requires_action`, which should fail the hold), releasing a hold that was already captured, Stripe declining while a hold is being released, and two "not yet" early returns. These are rare, but they're about money. **Plan: before the final release**, unit tests for those paths with the fake gateway, and a scheduled workflow that runs the sandbox tests weekly with the test key (#436).

**3. Background work is tested one pass at a time.** Ride reminders (Notifications), placing holds before departure (Payments' hold worker) and freeing detour plans (Routing) all run in the background. Each is tested by calling one pass directly with a fake clock against a real database (for example `ReminderScheduler.run_once`), not by starting the service and waiting. What's untested is the loop around it (`reminder_scheduler.py` lines 106–110, `hold_worker.py` 91%) and the startup wiring above. A reminder that's never scheduled because the loop didn't start would only show up in the logs. **Plan:** the wiring tests (startup, Routing's handler, the bell) are small and **will be done before the final release** (#437). Running the real loops at real times in a test would be slow and flaky, so we **accept** that gap: the deploy's `/health` checks confirm each service starts, and the loops log every failed pass.

**Carried over from Sprint 1.** We said we'd add tests for the trip validation rules in `trips/domain/entities.py` (more free seats than seats, a time without a timezone, an arrival before the departure). They're still missing (lines 36, 45, 51, 54). They're added with the wiring tests (#437). The other Sprint 1 plan, Playwright, is partly done: the post-deploy smoke test exists, the flow tests are gap 1.

### Sprint 1 report

Measured on `develop` at the end of Sprint 1, with 596 backend tests and 178 frontend tests. Backend 98% (98.5% of statements, 2,686 statements); frontend 79% of lines. The per-file reports are kept as PDFs: [backend](backend-coverage-sprint1.pdf), [frontend](frontend-coverage-sprint1.pdf). The per-package numbers are in the Sprint 2 table above for comparison.

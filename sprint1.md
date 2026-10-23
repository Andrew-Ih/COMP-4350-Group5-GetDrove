# Sprint 1: The first working slice

> Back to [README](README.md) · Previous: [Sprint 0](sprint0.md) · Milestone: [Sprint 1](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/milestone/1) · Board: [GetDrove project](https://github.com/users/Andrew-Ih/projects/3)

**Live site:** https://getdrove.duckdns.org · **Release:** `v0.1.0`, tag `sprint-1`

| | |
|---|---|
| [Sprint summary](#sprint-summary) | What we built and the value it adds |
| [Testing status](#testing-status) | Approach, tools, coverage, acceptance-criteria evidence |
| [CI status](#ci-status) | What runs, when, and what's next |
| [API documentation](#api-documentation) | Contracts between the frontend and the services |
| [Architecture](#architecture) | The current system |
| [Deployment](#deployment) | Live URL, test accounts, setup and deployment docs |
| [Reflection](#reflection) | Our Sprint 1 retro |
| [Known issues](#known-issues) | Deferred work and limitations |

## Sprint summary

Sprint 1 delivered the first end-to-end slice of GetDrove: **a UofM student can sign up, verify their email, log in, post a trip as a driver, and, as a rider, find only the trips whose real driving route passes within walking distance, with a private pickup point and their share of the cost.** It runs on the live site, on the same five services, gateway, database and routing engine designed in Sprint 0.

| User story | What a student can do now |
|---|---|
| [#2 Sign up with UofM email](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/2) | Sign up with an `@myumanitoba.ca` address, get a verification email with a 24-hour link (resend if it expires), and only then log in |
| [#89 Log in and stay logged in](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/89) | Log in, stay logged in across reloads and visits, and log out; every service checks the login itself |
| [#14 Post a trip](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/14) | Post a one-off trip to or from campus; its real driving route is computed and stored, and the driver sees the estimated arrival |
| [#22 Show only trips that pass near the rider](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/22) | Search by area, direction and time and see only trips they can walk to along real paths (not across a river), soonest first, with a pickup point and the route on a map |
| [#66 See my cost before requesting](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/66) | See their own share for each trip, based on how far they ride ($0.45/km, $2.00 minimum), with a one-line explanation |

Behind those stories, Sprint 1 also built the foundations the rest of the project relies on: event delivery between services (transactional outbox and Redis Streams), contract-first APIs with generated frontend types, a self-hosted routing engine (OSRM) with the Winnipeg map, CI on every pull request, and automatic deploys over HTTPS. The [milestone](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/milestone/1) and [board](https://github.com/users/Andrew-Ih/projects/3) have the full list of tasks and pull requests.

## Testing status

Testing approach, tools and mocking are documented in **[Testing strategy](docs/testing/testing-strategy.md)**. In short:

- **Backend unit tests** (pytest): domain rules on plain objects, and each use case with in-memory fakes for the database, clock, events and email.
- **Backend integration tests**: each service's real API and repositories against a throwaway **PostgreSQL + PostGIS, Redis and Mailpit** started by testcontainers, with the real migrations. They include the full signup → event → verification email flow, posting a trip with the route stored, and search with matching.
- **Contract tests**: every endpoint's inputs, errors and documented examples are checked against its OpenAPI contract, and CI fails if the frontend's generated types drift from the contracts.
- **Frontend** (Vitest, React Testing Library, MSW): form and search logic, and each screen as a user uses it, including loading, empty and error states.
- **Calls between services** (Trips → Routing, Trips → Payments, Routing → OSRM) are tested with fake HTTP responses covering every failure mode.

**Coverage** (end of Sprint 1, all 596 backend and 178 frontend tests passing): **backend 98%**, **frontend 79% of lines**. The [coverage report](docs/testing/testing-strategy.md#coverage) breaks this down per service and area and explains what's under-tested and why: mainly the Next.js pages and the map, which need a real browser (Playwright, planned for Sprint 2). Every CI run shows both totals on its summary page and attaches the full HTML reports ([latest run on develop](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/workflows/ci.yml?query=branch%3Adevelop)). Sprint 1 coverage screenshots: [Backend coverage](docs/testing/backend-coverage-sprint1.pdf) | [Frontend coverage](docs/testing/frontend-coverage-sprint1.pdf).

### Acceptance criteria evidence

Each user story's acceptance criteria are covered by tests (backend paths are under `services/<service>/tests/`, frontend under `web/src/`):

| Story | Acceptance criteria tested in |
|---|---|
| #2 Sign up | Backend: `accounts/.../integration/test_signup_api.py` (UofM-only emails, duplicate email), `test_verification_api.py` (24-hour link, expired link, resend), `test_login_api.py` (unverified can't log in); `notifications/.../integration/test_verification_email_flow.py` (the email is sent with a unique link). Frontend: `features/auth/ui/SignupForm.test.tsx`, `VerifyEmail.test.tsx`, `ResendButton.test.tsx` |
| #89 Log in | Backend: `accounts/.../integration/test_login_api.py` (one generic error, unverified told to verify), `test_session_api.py` (refresh, logout, reuse detection); `libs/common-security/tests/` (services check tokens with Accounts' public key). Frontend: `features/auth/ui/LoginForm.test.tsx`, `RequireAuth.test.tsx`, `shared/api/session.test.ts` (stays logged in, logout across tabs) |
| #14 Post a trip | Backend: `trips/tests/test_post_trip_api.py` (seats 1–6, no past departures, route computed and stored, nothing saved on failure), `test_upcoming_trips_api.py` (appears in the driver's upcoming trips); `routing/tests/test_compute_route_api.py`. Frontend: `features/drive/ui/PostTrip.test.tsx` (confirmation with the estimated duration) |
| #22 Near the rider | Backend: `routing/tests/test_match_api.py` and `test_match_rider.py` (corridor, walking distance along paths, a rider across the river doesn't match), `trips/tests/test_search_trips_api.py` (sorted by departure). Frontend: `features/ride/ui/TripResults.test.tsx` (results and the explained empty state) |
| #66 See my cost | Backend: `payments/tests/test_pricing.py` and `test_contract.py` (per-km, rounding, minimum, explanation), `trips/tests/test_search_trips.py` (priced on the distance this rider rides). Frontend: `features/ride/ui/TripResults.test.tsx` (cost and explanation shown) |

Where a criterion is only partly met this sprint, it's listed under [Known issues](#known-issues).

## CI status

**Workflow:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) ([runs](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/workflows/ci.yml))

**Trigger:** every pull request into `develop` or `main`, and every push to `develop`. Pull requests are where code is reviewed, so checks give feedback before a merge; running again on `develop` confirms the merged result still passes. It can also be run by hand.

**What runs** (two jobs in parallel):

| Backend | Frontend |
|---|---|
| Ruff format and lint | API types match the contracts (`npm run api:check`) |
| mypy, strict | ESLint, including the folder rules |
| Architecture rules per service (import-linter: e.g. the domain can't import FastAPI or SQLAlchemy) | TypeScript |
| All unit and integration tests, with coverage (integration tests start their own Postgres, Redis and Mailpit) | Tests with coverage |
| Coverage summary on the run page, HTML report as an artifact | Production build |

`bash scripts/check.sh` runs the same checks locally.

**Deployment** has its own workflow, [`deploy.yml`](.github/workflows/deploy.yml): every merge to `main` builds the images (the five services, the web app and OSRM with the Winnipeg map), deploys them to the server, checks OSRM answers a real route, and runs a smoke test over HTTPS ([Deployment](docs/deployment/deployment.md)).

**Next:** check that the contract files match the code (#178), Dependabot and CodeQL (#179), publish images on every merge to `develop` (#176), deploy alerts (#177), and Playwright end-to-end tests.

## API documentation

**[API documentation index](docs/api/README.md)**: every service's Swagger UI, its contract file, every endpoint (with which need a login), and the events between services.

- **Contracts:** [`contracts/openapi/`](contracts/openapi/) (one OpenAPI spec per service, generated from the code) and [`contracts/events/`](contracts/events/) (JSON Schema for each event). How they're written and changed, and the conventions all APIs share: [contracts/README.md](contracts/README.md).
- **Swagger UI:** `http://localhost/api/<service>/docs` with Docker Compose running, for example http://localhost/api/trips/docs.
- **Errors:** every error is Problem Details with a stable `code`, each documented with its own example ([common-web](libs/common-web/README.md)).
- The frontend's API types are generated from the contracts, so a contract change shows up as a type error.

## Architecture

**[Architecture](docs/architecture/architecture.md)** is updated for Sprint 1. The component diagram is coloured by what's built, with a status table and sequence diagrams for the two flows that run end to end (signup and email verification; posting a trip and finding it). An editable version is in [`getdrove-architecture.drawio`](docs/architecture/getdrove-architecture.drawio). Decisions are recorded as [ADRs](docs/architecture/adr/README.md); Sprint 1 added [0020](docs/architecture/adr/0020-password-hashing.md) (password hashing), [0021](docs/architecture/adr/0021-verification-email-requested-event.md) (the resend event) and [0022](docs/architecture/adr/0022-login-sessions.md) (login sessions).

## Deployment

**Live site:** **https://getdrove.duckdns.org**, on a Google Cloud VM with Docker Compose, HTTPS through Traefik and Let's Encrypt. Verification emails are sent for real through Brevo. The live site updates on every release to `main`; this submission is release `v0.1.0`.

**Test accounts:**

Every demo account uses the password **`GetDroveDemo2026`**. They're already verified, and they only hold made-up data.

| Role | Email | What to try |
|---|---|---|
| Rider | `getdrove.demo.priya@myumanitoba.ca` | Tap the map near Corydon Ave and search to campus, arriving around 08:30 on a weekday: the demo drivers' trips show up with a walk to the pickup point and a price |
| Rider | `getdrove.demo.owen@myumanitoba.ca` | Tap the map in Garden City, far from every route, and do the same search: the "no trips" state |
| Driver | `getdrove.demo.tomas@myumanitoba.ca` | Drives from St. Vital every weekday (08:00 to campus, 17:00 back); post another trip to see the clash warning |
| Driver | `getdrove.demo.maya@myumanitoba.ca` | Drives from Osborne Village Mon, Wed, Fri (07:45 to campus, 16:30 back) |

All eight demo people and their weekly commutes are listed in [infra/seed/README.md](infra/seed/README.md). The drivers' trips cover the next two weeks; the "Seed demo data" workflow tops them up. You can also sign up with any `@myumanitoba.ca` address and verify it from the email.

**Documentation:**

- [Local setup guide](docs/deployment/local-setup.md): from a fresh machine to the whole app running, tests and common problems (macOS and Windows)
- [Local Docker setup](docs/deployment/docker-setup.md) and [infra/README.md](infra/README.md): how the local stack works
- [Deployment](docs/deployment/deployment.md): how a release reaches the live site, the secrets it uses, checking a deploy, rolling back
- [Server setup](docs/deployment/server-setup.md): the VM, the domain and HTTPS

**Configuration and secrets:** every local setting has a default, so no `.env` is needed ([`.env.example`](.env.example) lists them). Production passwords, the token signing key and the email credentials are GitHub Secrets, written to the server's `.env` at deploy time; nothing secret is in the repository.

## Reflection

Our Sprint 1 retro: **[docs/retros/sprint1.md](docs/retros/sprint1.md)**. In short:

- **Proud of:** route matching. Riders only see trips they can actually walk to, measured with real walking times rather than a straight line, and pickup points never give away where the driver lives.
- **Could have been better:** the price quote work. An unclear task split meant two people built the same endpoint, and a merge into a feature branch skipped CI, costing an extra review round.
- **Testing in our workflow:** contracts and contract tests came first and unit tests were written alongside the code, but integration tests often came after, sometimes only when a review asked. Next sprint, each story's acceptance-criteria tests go in the same PR as the feature.

## Known issues

**Partly met acceptance criteria:**

- **#14:** the driver's upcoming trips are available from the API (`GET /api/trips/mine`, tested), but the "My trips" screen is Sprint 2 (#131).
- **#66:** the cost is shown on each search result rather than on a trip detail page (trip detail is Sprint 2). Keeping the shown price as the charged price is Sprint 2 (#69), when seat requests and payments exist.

**Deferred or not built yet:**

- Trip detail (`GET /api/trips/{id}`) and the rider's view of "my trips" (`role=rider`) still return 501, as their contracts say.
- Driver approval (licence, insurance, vehicle) is Sprint 2, so any verified student can post a trip for now.
- The map route (`/api/routing/trips/{id}/geometry`) is the full route, including where the driver starts; the contract trims it to start at the rider's pickup in Sprint 2. Pickup points already avoid the driver's end.
- No end-to-end browser tests yet (Playwright, Sprint 2), so the pages and the map are only covered by component tests and manual testing.

**Limitations:**

- **Free domain and email sender.** The site is on a free DuckDNS subdomain, so it depends on DuckDNS staying up. Verification emails are sent through Brevo from a Gmail address; because we can't prove that address to email providers the way we could with our own domain, the emails sometimes land in **junk/spam**. A domain of our own would fix both: Brevo could then send from it with a verified sender.

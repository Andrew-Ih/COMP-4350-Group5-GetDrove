# Regression testing

How we make sure a change doesn't break something that already worked (#181). In short:
**every automated test runs on every pull request and again on every merge into `develop`,
and a browser smoke test runs against the live site after every deploy.** A red run blocks
the merge, or (after a deploy) posts to Discord.

The kinds of tests and how to run them locally are in the
[testing strategy](testing-strategy.md); this page is about the regression process around
them. Numbers below are from the Delivery run for `develop` at the end of Sprint 2
([run #33](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44354061351),
18 November 2026) unless a different source is given.

## 1. Which tests are in the regression suite

All of them. There's no separate, smaller regression suite:

| Suite | Tests | What's in it |
|---|---|---|
| Backend (pytest) | **1,838 passed**, 4 skipped | Domain and use-case unit tests, adapter tests, API and contract tests for all five services and the shared libraries, and integration tests against real PostgreSQL + PostGIS, Redis and Mailpit (testcontainers). Includes the workspace test that runs Trips, Payments and Notifications together for a failed payment (`tests/integration/`) and the seat concurrency tests (`services/trips/tests/concurrency/`). |
| Frontend (Vitest) | **482 passed** in 53 files | Model, hook, component, API-layer and mock-API tests |
| Smoke test helpers (Playwright project `unit`) | 5 passed | The Winnipeg-time helper the browser smoke test uses |
| Browser smoke test (Playwright, `e2e/`) | 1 | Against the **live site after each deploy**: a demo rider logs in and searches for a ride |

Alongside the tests, the same runs fail on: formatting and lint (Ruff, ESLint), types (mypy
strict, TypeScript), architecture rules (import-linter in every service), contracts out of
date with the code (`scripts/export_openapi.py --check`, `npm run api:check`), and a frontend
production build that doesn't compile.

The 4 skipped backend tests are opt-in tests that use our real Stripe sandbox (a hold
placed, released three ways, and a declined card). They need a Stripe test key, which CI
doesn't have, so they're run by hand when the payment code changes:
`RUN_STRIPE_SANDBOX_HOLD=1` / `RUN_STRIPE_SANDBOX_FAILURE=1`. In CI, Payments is tested with
fakes and against `stripe-mock`.

## 2. How we chose them

We run the **whole suite every time**, and don't pick tests by what changed:

- **It's fast enough.** The backend tests take about two minutes and the frontend about
  45 seconds, in parallel (section 5). Choosing a subset would save a minute or two and risk
  missing a break across services.
- **Our breaks cross service boundaries.** A change in one service's contract, event or
  shared library can break another. Example: a sync of `develop` into the auto-accept
  feature ([#418](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/418)) failed
  ([run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44203058951))
  because a Trips change merged meanwhile (the trip detail returning the vehicle) broke
  two of the seat-request tests on that branch. A suite chosen by changed files wouldn't
  have run them.
- **No path filters.** Every pull request into `develop`, `main` or a `feature/*` branch
  runs both the backend and frontend jobs, even for a docs-only change. That also keeps the
  required status checks simple: they always report.

What we do choose is **which tests get written**: every bug fix comes with a test that
fails without the fix, and each risk we've identified gets a test aimed at it (see
section 7 for the seat concurrency test). Those rules are in the testing strategy's
[What a pull request needs](testing-strategy.md#what-a-pull-request-needs).

## 3. When it runs

| When | Workflow | What runs |
|---|---|---|
| Every push to a pull request into `develop`, `main` or `feature/*` | [CI](../../.github/workflows/ci.yml) | Everything in section 1 except the browser smoke test. A new push cancels the run still going for that pull request. |
| Every merge into `develop` | [Delivery](../../.github/workflows/delivery.yml) | The same checks again, on the merged code. Only if they pass are the eight Docker images built and published to GitHub Container Registry. |
| Every deploy to the live site (a release merged into `main`) | [Deploy](../../.github/workflows/deploy.yml) | `/health` of the home page and every service over HTTPS, a real route from OSRM, then the Playwright smoke test against https://getdrove.duckdns.org |
| By hand | Actions tab, or `bash scripts/check.sh` locally | CI can be run on any branch with "Run workflow"; `scripts/check.sh` runs the same checks on a laptop before pushing |
| Pull requests into `develop` and `main`, and every Monday | [CodeQL](../../.github/workflows/codeql.yml) | Security analysis of the Python and TypeScript code (#179) |

Running the suite again after the merge matters because a pull request is tested against
`develop` as it was when the branch was last updated. Our ruleset makes pull requests into
`develop` and `main` be up to date with the target branch before merging, and Delivery checks
the result anyway.

## 4. Tools

| Tool | Used for |
|---|---|
| **pytest** (+ pytest-asyncio, pytest-cov) | All backend tests and backend coverage |
| **testcontainers** | Throwaway PostgreSQL + PostGIS, Redis, Mailpit and stripe-mock containers for integration tests |
| **httpx** (`ASGITransport`) | Calling each service's real FastAPI app in tests |
| **Vitest** + React Testing Library + MSW | Frontend tests and coverage |
| **Playwright** | The browser smoke test after a deploy |
| **Ruff, mypy, import-linter, ESLint, TypeScript** | Static checks that run in the same jobs |
| **GitHub Actions** | Runs it all. Rulesets make the `Backend checks` and `Frontend checks` jobs required before merging. |
| **Discord webhook** | Tells the team when a deploy or the smoke test fails |

## 5. How long it takes

From GitHub Actions at the end of Sprint 2:

| What | Time |
|---|---|
| CI on a pull request (both jobs run in parallel) | **2.5 minutes** median over the last 132 successful runs since 4 November; 90% finished within 3.2 minutes (shortest 1.6, longest 7.9) |
| Backend job | about 3 minutes, of which the tests take **2 min 11 s** (1,838 tests, including starting the containers) |
| Frontend job | about 2 to 2.5 minutes, of which the tests take **45 s** (482 tests); installing dependencies takes about a minute |
| Delivery on `develop` (checks, then building and publishing the images) | **3.7 minutes** median over all 33 runs (2.8 to 6.1) |
| Deploy, including the smoke test | about 4 to 5 minutes. Measured on the Sprint 1 releases, before the smoke test was added; the v0.2.0 release (#187) will be the first deploy with it. |

The longest single step is building the web image (about 3 minutes in Delivery). It runs
after the tests, so it doesn't slow down finding a failure.

## 6. What happens when it fails

**On a pull request:** the `Backend checks` or `Frontend checks` job goes red, and GitHub
won't let the pull request be merged. Both are required status checks in our rulesets for
`develop`, `main` and every `feature/*` branch, together with one approving review. The
**author fixes it** on their branch. If the failure is caused by someone else's merge (as in
the sync above), the author of the branch being synced fixes it, and asks the owner of the
other change if the fix touches their code. Failed runs keep their test report and coverage as downloadable artifacts for 14 days.

Since 4 November, 5 of the last 150 CI runs failed and 12 were cancelled by a newer push.
Each failure was fixed with another push to the same branch, and the required checks mean
only a green run can be merged.

**On `develop` (Delivery):** no images are published for that commit, so it can't be
released. Whoever merged it fixes it straight away or reverts it. This hasn't happened: all
33 Delivery runs passed.

**After a deploy:** if the deploy, the health checks or the browser smoke test fails, the
run goes red and the **Alert on Discord** job posts the failed run's link to the team
channel. The Playwright screenshot and trace are kept as the `smoke-test-report` artifact. The
person who ran the release looks first. If the live site is broken, they **roll back** by
running Deploy by hand with `image_tag` set to the previous release's commit (see
[deployment](../deployment/deployment.md)), then fix forward through a pull request as
usual. Running Deploy by hand with `test_alert` ticked checks the alert itself: nothing is
deployed and the smoke test fails on purpose.

**Flaky tests** are treated as failures, not rerun until they pass. When a frontend test for
a driver's posted-trip requests failed only sometimes, it was fixed rather than retried
([#399](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/399)).

## 7. Example: a regression test for a past risk

Selling the same seat twice was one of our biggest risks: two drivers' clicks, or a driver's
accept racing an auto-accept rule, could both take the last seat. Story #46 fixed that with
row locks in PostgreSQL, and #50 added
[`services/trips/tests/concurrency/test_seat_oversell.py`](../../services/trips/tests/concurrency/test_seat_oversell.py)
so it stays fixed. It runs on real PostgreSQL with every pull request:

- 20 riders accepted at the same moment for **1 seat**: exactly one gets it, 19 get
  `409 seat_taken`, and exactly one `RequestAccepted` event is published. It runs three
  times in each run, to show it isn't flaky.
- 20 riders for **3 seats**: exactly three are accepted.
- An **auto-accept racing a manual accept** for the last seat: only one wins.
- A **cancelled seat** is taken by the next rider straight away.

If anyone removes the lock or changes how seats are counted, these fail on that pull request.

## Evidence

- CI on a pull request: [run for #432 (payment card)](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44353361571), both jobs green in 3.1 minutes
- Delivery on `develop`: [run #33](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44354061351), checks then the eight images, 6.1 minutes
- A regression caught before merging: [failed run on the sync for #41](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44203058951), fixed in [#418](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/418)
- All runs: [Actions](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions)

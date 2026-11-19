# Sprint 2: The core loop

> Back to [README](README.md) · Previous: [Sprint 1](sprint1.md) · Milestone: [Sprint 2](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/milestone/2) · Board: [GetDrove project](https://github.com/users/Andrew-Ih/projects/3)

**Live site:** https://getdrove.duckdns.org · **Release:** `v0.2.3`, tag `sprint-2`

| | |
|---|---|
| [Sprint summary](#sprint-summary) | What we built and the value it adds |
| [Regression testing](#regression-testing) | What runs, when, how long, what happens on failure |
| [Testing status and gaps](#testing-status-and-gaps) | Coverage, what it means, and the gaps we know about |
| [CI/CD status](#cicd-status) | Delivery on `develop`, deployment from `main`, secrets, alerts |
| [Live deployment](#live-deployment) | URL, test accounts, the Stripe test card |
| [Cross-team testing](#cross-team-testing) | Our review of another team, and the feedback we got |
| [API and architecture](#api-and-architecture) | Contracts, diagrams, new decisions |
| [Reflection and risk](#reflection-and-risk) | Retro, individual reflections, risks for the final iteration |
| [Known issues](#known-issues) | Partly met criteria and deferred work |

## Sprint summary

Sprint 1 let a student find a ride. Sprint 2 lets them **get one**: **a rider asks for a seat with a private pickup point and a known cost, the driver sees how many minutes each request adds and accepts it (or auto-accept does), the seat can't be sold twice, the rider's share is held on their card, and both of them are notified and reminded.** Drivers must now be approved before they post, can post a whole term of weekday trips at once, and can cancel one trip or the rest of a series. All of it runs on the live site.

| User story | What a student can do now |
|---|---|
| [#8 Upload licence and insurance for driver approval](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/8) | A driver uploads their licence and insurance and saves their vehicle; an admin reviews them on an admin page and approves or rejects with a reason. Only approved drivers can post, and approval takes effect straight away. |
| [#15 Post a recurring weekday trip](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/15) | Post the same commute on chosen weekdays until an end date, in one go; cancel one day or the rest of the series |
| [#28 Suggested pickup point on the route](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/28) | See a pickup point on the driver's route with the walking time to it, and ask for a different one |
| [#34 Request a seat on a trip](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/34) | Ask for a seat from the trip detail page; see it pending, then accepted or declined; cancel it. Requests that clash with another of their rides are refused. |
| [#35 Detour cost per request](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/35) | As a driver, see how many minutes each request adds and where the pickup falls in the order, before accepting |
| [#41 Auto-accept rules](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/41) | As a driver, accept requests automatically when they add less than a chosen detour and the rider's rating is high enough |
| [#46 Seats cannot be oversold](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/46) | However many accepts happen at once, exactly the number of seats are filled; the others are told the seat was just taken |
| [#52 Trip reminder before departure](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/52) | Get a reminder 30 minutes before a ride, which is cancelled if the ride is |
| [#129 See my upcoming trips](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/129) | My trips: upcoming and past rides and drives in one list, with each request's status |
| [#144 Get notified about my requests and trips](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/144) | A bell and an email for every request, decision, cancellation, approval and payment problem |
| [#150 Add a payment card](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/150) | Save a card once (Stripe Elements; card details never reach our servers), needed before asking for a seat |
| [#257 Type an address to choose your area](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/257) | Type an address or place for pickup, drop-off or a trip's start, press Search and pick a match, instead of only tapping the map ([ADR 0027](docs/architecture/adr/0027-geocoding.md)) |
| [#67 Charge only after the trip happens](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/67) (part) | The rider's share is **held** on their card when they're accepted and **released** if the ride is declined or cancelled. Charging after the trip needs the trip to be completed, which is Sprint 3. |
| [#20 Cancel a posted trip](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/20) (part) | Cancel a trip that hasn't started; riders are told and their holds released. Recording late cancellations on the driver's record is Sprint 3 (#134). |

Behind the stories, Sprint 2 also built: the events that tie the services together (14 event types through the outbox, each handled once), Trips' own copy of approved drivers, a Redis cache of detour plans, a background hold worker in Payments and a reminder scheduler in Notifications, a concurrency test for overselling, CD on every merge to `develop` and on every release, a browser smoke test against the live site with Discord alerts, CodeQL and Dependabot, and demo data that seeds every state. The [milestone](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/milestone/2) and [board](https://github.com/users/Andrew-Ih/projects/3) list every task and pull request.

## Regression testing

**[Regression testing](docs/testing/regression.md)** answers each question in detail, with links to runs. In short:

- **What runs:** the whole suite, every time: **1,838 backend tests** (unit, contract and integration tests against real PostgreSQL + PostGIS, Redis, Mailpit and stripe-mock), **482 frontend tests**, plus lint, strict types, architecture rules and the contract checks. After every deploy, a **Playwright** test logs in to the live site as a demo rider and searches.
- **How we chose it:** no subset and no path filters. The suite is fast enough, and our breaks cross services: a sync of `develop` into a feature branch failed because another team member's change broke two of that branch's tests ([run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44203058951)), which a suite picked by changed files wouldn't have run.
- **When:** on every pull request (CI), again on every merge into `develop` (Delivery), and against the live site after every deploy.
- **How long:** **2.5 minutes** for a pull request (median of 132 runs; backend tests 2 min 11 s, frontend tests 45 s, in parallel), **3.7 minutes** for Delivery.
- **On failure:** both jobs are required checks, so a red run can't be merged; the author fixes it. A failed deploy or smoke test posts to Discord and can be rolled back in a minute. Flaky tests are fixed, not rerun.
- **A regression test for a past risk:** [`test_seat_oversell.py`](services/trips/tests/concurrency/test_seat_oversell.py) (#50) fires 20 accepts at once for one seat on real PostgreSQL, three times per run, and checks exactly one wins.

## Testing status and gaps

Approach, tools and mocking: **[Testing strategy](docs/testing/testing-strategy.md)**. Coverage and gaps: **[its coverage section](docs/testing/testing-strategy.md#coverage)**.

**Coverage** (end of Sprint 2, `develop` at `d586b8b`, all tests passing): **backend 97%** (98.1% of statements, on 2.6 times the code of Sprint 1), **frontend 86.5% of lines** (up from 79%). Per-file reports: [backend](docs/testing/backend-coverage-sprint2.pdf) · [frontend](docs/testing/frontend-coverage-sprint2.pdf).

**What it means:** the rules that matter most are the best covered: requests, accepting, auto-accept, cancellations and recurring trips in Trips (99%), approval in Accounts (99.7%), and the new screens (90–98%). The low spots share a cause: code that only runs when a service starts, or in a real browser.

**The gaps, and what we'll do:**

1. **Pages, the map and Stripe's card field are never tested in a browser** (0–7%), so a broken page link or a card form that doesn't load would only be caught by hand. Playwright tests of request → accept → hold in CI, before the final release: [#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435).
2. **Stripe is only faked in CI.** The real sandbox tests are opt-in, and a few rare hold paths have no test (3-D Secure when the hold is placed, Stripe declining during a release). Unit tests and a weekly sandbox run: [#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436).
3. **Background work and startup wiring.** Reminders, holds and Routing's cache are tested one pass at a time; the startup wiring isn't tested. Wiring tests before the final release, plus the trip validation tests we promised in Sprint 1 and didn't write: [#437](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/437). Running the real loops at real times is an accepted gap (slow and flaky; the deploy's health checks and the logs cover it).

### Acceptance criteria evidence

Backend paths are under `services/<service>/tests/`, frontend under `web/src/`.

| Story | Acceptance criteria tested in |
|---|---|
| #8 Driver approval | Accounts: `integration/test_driver_documents_api.py`, `test_driver_vehicle_api.py`, `test_admin_drivers_api.py` (approve, reject with a reason, events). Trips: `test_account_events.py`, `test_post_trip_api.py` (`403 driver_not_approved`). Web: `features/driver/ui/DriverPage.test.tsx`, `AdminDrivers.test.tsx`, `DriverGate.test.tsx` |
| #15 Recurring trips | Trips: `test_recurrence.py`, `test_post_recurring_trip_api.py`, `test_trip_series_repository.py`, `test_cancel_series_api.py`. Web: `features/drive/ui/PostTrip.test.tsx` |
| #28 Pickup point | Routing: `test_match_rider.py`, `test_location_privacy.py`. Trips: `test_request_seat_exclude.py` (choose a different point). Web: `features/ride/ui/TripDetail.test.tsx` |
| #34 Request a seat | Trips: `test_request_eligibility.py`, `test_request_seat.py`, `test_request_seat_api.py` (overlap, card required, trip open), `test_decide_request_api.py`. Web: `features/ride/ui/TripDetail.test.tsx`, `features/my-trips/ui/MyTrips.test.tsx` |
| #35 Detour cost | Routing: `test_detour.py`, `test_insertion.py`, `test_detour_api.py`. Trips: `test_trip_requests_api.py`. Web: `features/drive/ui/TripRequests.test.tsx` |
| #41 Auto-accept | Trips: `test_auto_accept.py`, `test_auto_accept_requests.py`, `test_auto_accept_api.py`. Web: `features/auto-accept/ui/AutoAcceptSettings.test.tsx` |
| #46 No overselling | Trips: `concurrency/test_seat_oversell.py`, `test_seat_request_repository.py` |
| #52 Reminders | Notifications: `domain/test_reminders.py`, `application/test_trip_reminders.py`, `integration/test_reminder_events.py`, `test_reminder_scheduler.py` |
| #129 My trips | Trips: `test_my_trips_api.py`, `test_rider_trips.py`. Web: `features/my-trips/ui/MyTrips.test.tsx` |
| #144 Notifications | Notifications: `application/test_trip_events.py`, `test_notify.py`, `integration/test_notification_events.py`, `test_all_handlers.py`. Web: `features/notifications/ui/NotificationBell.test.tsx`, `NotificationsPage.test.tsx` |
| #150 Payment card | Payments: `test_cards.py`, `test_customer_repository.py`, `test_saved_card_lookup.py`. Trips: `test_card_status_adapter.py`. Web: `features/payments/ui/AddCard.test.tsx` |
| #67 Holds (part) | Payments: `test_holds.py`, `test_hold_timing.py`, `test_hold_pipeline.py`, `test_stripe_mock.py`; opt-in `test_stripe_sandbox_hold.py`. Trips: `test_payment_failed.py`. Workspace: `tests/integration/test_payment_failure_flow.py` |
| #20 Cancel a trip (part) | Trips: `test_cancel_trip.py`, `test_cancel_series_api.py`. Web: `features/my-trips/ui/MyTrips.test.tsx` |

## CI/CD status

| Workflow | Trigger | What it does | Environment |
|---|---|---|---|
| [CI](.github/workflows/ci.yml) | Every pull request into `develop`, `main` or `feature/*` | Every check and test (two jobs in parallel, both required to merge) | None |
| [Delivery](.github/workflows/delivery.yml) | **Every merge into `develop`** | CI again, then builds the eight images and publishes them to GitHub Container Registry, tagged with the commit | None: deployable images ([33 runs, all green](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/workflows/delivery.yml)) |
| [Deploy](.github/workflows/deploy.yml) | **Every merge into `main`** (a release or hotfix), or by hand for a rollback | Reuses the images built for `develop`, deploys them over SSH, checks a real OSRM route, runs `/health` and a Playwright smoke test against the live site, posts to Discord if anything fails | **The live site** |
| [Seed demo data](.github/workflows/seed-demo.yml) | By hand | Demo accounts, approvals, cards, trips and requests on the live site | The live site's demo data |
| [CodeQL](.github/workflows/codeql.yml) | Pull requests, weekly | Security analysis (advisory in Sprint 2) | None |

**Why the live site tracks `main`, not `develop`:** the live site is what the instructor and other teams test, so it should only change with reviewed, released code. Every merge to `develop` is still tested and packaged automatically, and a release deploys exactly the images that passed on `develop` ([ADR 0016](docs/architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md), [ADR 0026](docs/architecture/adr/0026-releases-reuse-develop-images.md)).

**Secrets:** database passwords, the token signing key, Brevo, the Stripe test secret key, the deploy key, the demo password and the Discord webhook are GitHub Secrets; the server's `.env` is written from them at deploy time. Nothing secret is in the repository. Names and what each is for: [deployment.md § Secrets](docs/deployment/deployment.md#3-secrets).

**Success and failure:** each run is green or red in the Actions tab and on the commit; a failed deploy or smoke test is also posted to our Discord. Rollback: run Deploy with an earlier release's commit SHA ([deployment.md § Rolling back](docs/deployment/deployment.md#5-rolling-back)).

**Evidence:** a [CI run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44353361571) · a [Delivery run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44354061351) · a [Deploy run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44468394807) (v0.2.2: images reused from `develop`, deployed, smoke test passed) · a [failed Deploy run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44460186633) (v0.2.0: the smoke test couldn't start, and the alert reached our Discord)

## Live deployment

**Live site:** **https://getdrove.duckdns.org** (Google Cloud VM, Docker Compose, HTTPS through Traefik and Let's Encrypt; real emails through Brevo).

**Test accounts.** Every demo account uses the password **`GetDroveDemo2026`**. They're already verified and hold made-up data. Demo emails aren't actually sent; their notifications are in the bell.

| Role | Email | What to try |
|---|---|---|
| Rider | `getdrove.demo.priya@myumanitoba.ca` | Has a card and an **accepted** seat on Maya's next trip to campus: see it in My trips, the bell, and the trip detail with the driver's car |
| Rider | `getdrove.demo.noah@myumanitoba.ca` | Has a card and a **pending** request on the same trip: cancel it, or log in as Maya to accept it |
| Rider | `getdrove.demo.owen@myumanitoba.ca` | **No card:** asking for a seat tells him to add one first, with a link to the card page. Use the test card below. |
| Driver | `getdrove.demo.maya@myumanitoba.ca` | Open her next trip to campus: Priya accepted, Noah waiting, with the minutes each adds. Accept Noah, turn on auto-accept, or cancel the trip. |
| Driver | `getdrove.demo.aisha@myumanitoba.ca` | Her Tue/Thu trips to campus are a **recurring series**: cancel one day or the rest |
| Driver | `getdrove.demo.sam@myumanitoba.ca` | **Pending approval:** sees that he can't post yet |

All the demo people, their commutes and cars are in [infra/seed/README.md](infra/seed/README.md). You can also sign up with any `@myumanitoba.ca` address. The admin review page (**Driver applications** in the account menu) needs an admin account; ask us and we'll give yours the role, or we'll show it in the demo.

**Stripe test card:** **`4242 4242 4242 4242`**, any future expiry date, any CVC, any 5-digit ZIP (it's a US test card; Stripe's Canadian test card `4000 0012 4000 0000` takes a Canadian postal code). Stripe is in test mode: holds appear in our Stripe test dashboard and no real money moves. `4000 0000 0000 0002` is declined, to see the failure message.

**Documentation:** [Local setup](docs/deployment/local-setup.md) · [Local Docker setup](docs/deployment/docker-setup.md) · [Deployment](docs/deployment/deployment.md) · [Server setup](docs/deployment/server-setup.md) · [Demo data](infra/seed/README.md)

## Cross-team testing

**Our review of another team:** we black-box tested **BisonRides** on their live site (https://bisonrides.vercel.app, desktop Chrome, Nov 18) and filed three issues on their repo, each with steps to reproduce, expected and actual behaviour, and a suggestion:

| Issue | Type · severity | What we found |
|---|---|---|
| [#96 Unknown or mistyped URLs show a blank white page](https://github.com/BisonRIdes/Comp4350Project/issues/96) | Bug · Low | Any address that isn't a real page (e.g. `/abc`, `/forgot-password`) shows a blank page with no way back; we suggested a branded 404 page with a link home. |
| [#97 No way to reset a forgotten password](https://github.com/BisonRIdes/Comp4350Project/issues/97) | Missing feature · Medium | There's no "Forgot password?" link, so a student who forgets their password is locked out; we suggested reusing their verification-email flow for a time-limited reset link. |
| [#98 Some rides on Find Ride show no price](https://github.com/BisonRIdes/Comp4350Project/issues/98) | Bug · Medium | Some rides show a price and others none, so riders can't tell whether a ride is free or the price is missing; we suggested always showing a price, or a clear "Free" / "Price not set" label. |

**Feedback we received:** the other team's feedback on GetDrove hadn't arrived by the Sprint 2 deadline. The instructor told us cross-team testing isn't required for this iteration, so we kept our review above and will respond to their feedback when it arrives: we'll file each item as an issue labelled [`feedback`](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Afeedback) and mark it Accepted, Deferred or Rejected with a reason. The instructor's feedback from this sprint, that verifying your email should log you in, is accepted and planned for Sprint 3 (the design is ready as ADR 0028).

## API and architecture

- **[API documentation](docs/api/README.md):** every service's Swagger UI and contract, every endpoint (and which need a login), and the events. The contracts in [`contracts/openapi/`](contracts/openapi/) and [`contracts/events/`](contracts/events/) are generated from the code, and CI fails if they or the frontend's types fall out of date. Sprint 2 added the request, decision, auto-accept, series, cancellation, driver, admin, profile, notification and card endpoints, and 11 events.
- **[Architecture](docs/architecture/architecture.md)**, updated for Sprint 2: the component diagram (gateway, services, PostgreSQL, Redis Streams, OSRM, Stripe, Brevo, the VM) coloured by what's built, every call and event between services, the Sprint 2 status, the **request → accept → hold → notify** sequence as built, and the CI/CD pipeline. Editable version: [`getdrove-architecture.drawio`](docs/architecture/getdrove-architecture.drawio).
- **New decisions:** [0023](docs/architecture/adr/0023-approved-drivers-read-model.md) (Trips' copy of approved drivers), [0024](docs/architecture/adr/0024-seat-counting.md) (seats taken with one guarded update), [0025](docs/architecture/adr/0025-payment-holds.md) (holds by a worker on a saved card), [0026](docs/architecture/adr/0026-releases-reuse-develop-images.md) (releases reuse `develop`'s images).

## Reflection and risk

Our Sprint 2 retro: **[docs/retros/sprint2.md](docs/retros/sprint2.md)**. <!-- TODO(#185): two or three lines from the retro -->

### Work we're proud of

<!-- TODO(#185): the team picks one or two; candidates below, with why -->

- **No overselling, proven under load ([#46](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/46), [#425](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/425)).** Taking a seat is one guarded database update, and a concurrency test fires 20 accepts at once at real PostgreSQL on every pull request, including auto-accept racing the driver.
- **Holds that survive anything ([ADR 0025](docs/architecture/adr/0025-payment-holds.md)).** Accepting never waits for Stripe; the hold worker places the hold from the event with an idempotency key, so a crash or a repeated event never holds twice, and a card that fails frees the seat.

### Individual reflections

Each of us answered one of the four prompts from the Sprint 2 instructions.

<!-- TODO(#185): each person fills in their own row; prompts from the Sprint 2 instructions -->

| Who | Prompt | Reflection |
|---|---|---|
| Andrew | Prompt #1 | The change I'm happiest with is how we release. In Sprint 1, `main` rebuilt every image when we deployed, so what went live wasn't exactly what we'd tested. Now `develop` builds and publishes the images once, and a release to `main` reuses those same images, deploys them, runs a browser smoke test against the live site, and posts to our Discord if anything fails ([ADR 0026](docs/architecture/adr/0026-releases-reuse-develop-images.md)). Releasing 0.2.x proved why: when GitHub's runners moved to Ubuntu 26.04 and the map download site refused GitHub, the deploy failed loudly, the live site stayed up, and we fixed it the same night. |
| Chimdi |Prompt #4  | I think the most important technical risk going into the final iteration is whether our services work together reliably through the complete booking flow. Our unit and integration tests cover individual components well, but our browser smoke test only checks login and trip search. Problems involving seat requests, driver acceptance, payment holds, or notifications could still appear when those features run together. Adding a Playwright test for that complete flow would give me more confidence before the final release. |
| Daniel |Prompt #2 | Daniel – Prompt #2 – In Sprint 1 we said our tasks weren’t clear about when they were finished, so in Sprint 2 every task got a “Done when” checklist. Reviewers now check each pull request against that list. This helped me directly: a review found that unapproved drivers could still post recurring trips, and that auto-accept sent drivers two messages, and I fixed both before they were merged.|
| Farouk | Prompt #3| One of the biggest challenges with our current CI/CD process is managing dependencies between pull requests, especially when multiple features are being developed simultaneously. Some pull requests depend on changes from other branches, which can delay reviews and merging even when their individual checks pass. This creates additional work because branches need to be rebased and tests rerun whenever dependent code changes. I think we could improve this by keeping pull requests smaller, reducing unnecessary branch dependencies, and coordinating merge order more effectively.|
| Kelvin | | |
| Rayan | | |

### Risks for the final iteration

| Risk | Why it matters | What we'll do |
|---|---|---|
| **Trip execution and capture land together** | Charging after the trip (#71), no-show charges (#155), ratings and earnings all depend on trips being completed (#156). If execution is late, the money story stays half done for the final demo. | Start #156 first in Sprint 3; capture is already built and only needs the `TripCompleted` event. |
| **No browser tests of the main flow** | A broken page or card form would only be caught by hand, and Sprint 3 adds more screens. | Playwright flow tests in CI early in Sprint 3 ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435)). |
| **Real Stripe behaviour** | CI only fakes Stripe; holds expire after 7 days and 3-D Secure cards behave differently. | Weekly sandbox tests and the untested hold paths ([#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436)). |
| **Load and security hardening in a short final sprint** | JMeter load testing (#191) and making CodeQL required (#188) are course requirements, and Routing is our slowest service. | Feature freeze at the end of week 8; load test Routing's search and detours first. |
| **The free hosting ends** | The Google Cloud trial credit runs out in early January 2027, and the site is on a free DuckDNS name. | Enough for the term; the VM is shut down after the final demo. |
| **Feature branches drifting from `develop`** | Long-lived story branches needed repeated syncs this sprint, and some broke tests that passed on their own. | Smaller stories, and syncing `develop` into a feature branch at least every two days. |

## Known issues

**Partly met acceptance criteria:**

- **#67 Charge only after the trip happens:** holds and releases work; capturing after the trip (#71) and charging no-shows (#155) need trip completion (#156), Sprint 3.
- **#20 Cancel a posted trip:** recording late cancellations on the driver's record is Sprint 3 (#134). The `DriverLateCancellation` event is already published.

**Deferred or not built yet:** trip execution (start, picked up, no-show, complete), capture and earnings, writing ratings, blocks and reports, trip chat, share links, versioned images on DockerHub (#189).

**Limitations:**

- **A card can be replaced but not removed.** Adding a new card makes it the one used; the old one stays saved in Stripe. Removing a card is Sprint 3.

- **A rider is told they're in before their card is held.** If the hold then fails, they lose the seat and are told why. Requiring a saved card before requesting makes this rare ([ADR 0025](docs/architecture/adr/0025-payment-holds.md)).
- **Past rides show their last request status** ("Confirmed") rather than "Completed", because nothing completes a trip yet (#156).
- **Free domain and email sender**, as in Sprint 1: emails from our Gmail sender sometimes land in spam.

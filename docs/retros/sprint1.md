# Sprint 1 retro

> Back to [Sprint 1](../../sprint1.md)

<!-- DRAFT: written from the sprint's PRs and reviews as a starting point. Go through it at
     the retro meeting, change anything the team sees differently, then delete this note. -->

**Held:** _date_ · **Facilitator:** _name_ · **Attended:** _names_

## What we're proud of

**Route matching ([#239](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/239)).** The core promise of GetDrove is that a rider only sees trips that actually pass near them. Instead of a straight-line radius, Routing samples each stored route every 100 m, finds the points within 800 m with one PostGIS query, then asks OSRM for real walking times to them, so a rider across the river from a route doesn't match even though it's close on the map. It also protects drivers: pickup points are never offered near either end of a route, so a rider can't work out where the driver lives. It came with thorough tests (every OSRM failure mode, the river case, the privacy rule), and running OSRM ourselves (#23, #233) with the map built into the images means it works the same on every laptop and on the live site.

## What could have been better

**Splitting and merging the price quote work ([#237](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/237), [#238](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/238), [#240](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/240)).** Two people built the same quote endpoint in parallel, because one task (#69) had no "done when" and overlapped with #99. One PR was closed. The other was merged into a feature branch, where CI doesn't run, so it reached `develop` through a second PR and a second review. Clearer task descriptions before assigning, and checking the PR's base branch, would have avoided the duplicate work and the extra round.

A smaller one in the same spirit: the Trips and Routing database tests first needed a Postgres started by hand, unlike the other services, so anyone running the full suite got dozens of failures. That's fixed ([#245](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/245)): every service's tests now start their own database.

## How testing fit into our workflow

- **Contracts first.** The sprint started with the API contracts (#108) and endpoints that returned 501, so contract tests (routes exist, validate input, document every error) came before any implementation, and the frontend was built and tested against mock APIs typed from the same contracts.
- **Unit tests during implementation.** Domain rules and use cases were mostly written with their unit tests, using in-memory fakes, which made the rules easy to test in isolation.
- **Integration tests often came after,** and sometimes only when a reviewer asked for them, for example the real database test for the upcoming-trips query (#236) and the halfway rounding cases for pricing (#240). Reviews were where several gaps were caught.
- **Would more test-first have helped?** For pure rules (pricing, search windows, route sampling), yes: they're easy to specify as test cases first, and the rounding review comments would have been caught earlier. For wiring code (the database, the HTTP clients between services), writing the integration test first would have been harder until the shared test setup (testcontainers) existed in every service. For Sprint 2 we'll write each story's acceptance criteria as tests in the same PR, rather than after review.

## Process

- **Git workflow:** mostly followed (feature and task branches off `develop`, squash merges, releases to `main`). Mistakes were PRs opened against the wrong base (GitHub defaults to `main`), and PR titles that didn't follow the commit format, which matters because the title becomes the commit on `develop`.
- **Reviews:** thorough, and they caught real problems (privacy in logs, duplicated code, missing tests), but some PRs went through several rounds. Running `bash scripts/check.sh` before opening a PR would save a round.
- **Technical debt:** mid-sprint we agreed to fix problems when they're found instead of leaving "fine for now" notes, which is why the test databases, OSRM in production and HTTPS were all finished before the release.
- **Working agreement:** _still fits? anything to change?_

## What we'll change for Sprint 2

1. Every task gets a "done when" before it's assigned, and overlapping tasks are merged or clarified on the board.
2. Acceptance-criteria tests go in the same PR as the feature.
3. Check the PR base and title format when opening a PR, and run `scripts/check.sh` first.
4. _anything else from the meeting_

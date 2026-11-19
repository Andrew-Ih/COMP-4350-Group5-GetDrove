# Sprint 2 retro

> Back to [Sprint 2](../../sprint2.md) · Previous: [Sprint 1 retro](sprint1.md)

**Reviewed by:** Andrew, Chimdi, Daniel, Farouk, Kelvin, Rayan, November 19, 2026

## Did we do what we said in Sprint 1?

The Sprint 1 retro ended with four changes. For each: did it happen, and did it help?

| Change we agreed | What happened | Keep? |
|---|---|---|
| 1. Every task gets a "done when" before it's assigned | Mostly. Stories had acceptance criteria and most tasks had a "done when", but some tasks created mid-sprint had no label, milestone or parent until we cleaned up the board at the end. | Yes |
| 2. Acceptance-criteria tests go in the same PR as the feature | Mostly. Feature pull requests came with their tests, but the overselling test ([#50](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/50)) came as its own task after the fix ([#47](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/47)). | Yes |
| 3. Check the PR base and title, and run `scripts/check.sh`, before opening a PR | Yes, and it showed: 5 of the last 150 CI runs failed, all fixed before merging. One sync pull request still used the wrong head branch. | Yes |
| 4. Try each new screen as a first-time user on the live site | Late. We did it after the first release, and it found real gaps (no admin link [#466](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/466), no way to remove a card [#464](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/464), a demo rider who couldn't be seated). Doing it before releasing would have caught them sooner. | Yes, on every release (Sprint 3 change 2) |

## What we're proud of

- **GetDrove works end to end.** A student can sign up, add a card, find a ride by typing an address, request a seat, and get accepted, with their share held on their card and a notification at every step. A driver can post one-off or recurring trips, see what each request adds to their drive, and accept or decline. That flow runs across five services (Accounts, Trips, Routing, Payments, Notifications) that talk to each other through API calls and 14 kinds of events, on the live site.
- **Lots of features without breaking what was there.** We finished 12 stories this sprint, and parts of two more, and the 1,838 backend and 482 frontend tests, run on every pull request, kept the Sprint 1 features working. Coverage went up on the frontend and held on the backend, and the gaps we know about are written down ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435), [#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436), [#437](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/437)), not hidden.
- **The frontend looks good and is honest about its gaps.** The screens are consistent and work on a phone. When live testing found gaps (no admin link, no way to remove a card, a US-only postal box with the test card), we fixed what we could before the deadline ([#466](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/466)) and filed the rest for Sprint 3 ([#464](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/464)).
- **Decisions are written down.** Every significant choice this sprint has an ADR (0023 to 0027: approved drivers, seat counting, payment holds, releases, geocoding), so anyone can see why something was built the way it was.
- **CI/CD we can trust.** Every pull request runs the full checks; every merge to `develop` builds the images; a release to `main` reuses those exact images, deploys them, runs a smoke test against the live site, and posts to our Discord if anything fails. Dependabot ([#179](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/179)) now opens pull requests for outdated or vulnerable dependencies, and CodeQL scans the code for security problems.
- **Communication and timing.** We talked through problems on Discord as they came up, and when one person's work blocked someone else's (contracts before implementations, cards before payment holds), we got it done early enough that everyone had time to finish theirs. Work came in on time.

## What could have been better

- **Our branching strategy was too complex.** Each story had its own long-lived feature branch, every task went into that branch, and the story only reached `develop` at the end. Stories that ran for a week or more (#8, #41, #46, #67, #150) fell behind `develop` and needed several sync pull requests each; one sync used `develop` itself as its head branch and had to be redone, and one broke two tests that had passed on the story branch ([run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44203058951)). It also blocked us: work that depended on another story had to wait for that whole story to reach `develop`, and payment holds ([#67](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/67)) reached `develop` before saved cards ([#150](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/150)), so nothing could be released until both were done. **Next time:** short-lived task branches straight from `develop` (see below).
- **We released only at the end.** The first release to `main` went out the night before the deadline and took four attempts: GitHub moved its runners to Ubuntu 26.04 (our browser test couldn't install), clicking "Update branch" on the release made it rebuild every image, and the map download site then refused GitHub's runners. Each problem was fixed that night, but problems like these should surface early in the sprint, not on the last evening. **Next time:** release as soon as a story is done.
- **Some pull requests took several review rounds** (for example #400, #403, #410, #419, #425, #427). Most rounds caught real problems, but large pull requests were slow to review. Smaller tasks with smaller pull requests should help.

## How testing fit into our workflow

Better than Sprint 1: most acceptance-criteria tests came in the same pull request as the feature, CI ran all 1,838 backend and 482 frontend tests on every pull request, and a flaky frontend test was fixed rather than retried ([#399](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/399)). Coverage went up on the frontend (79% → 86.5%) and held on the backend (98% → 97%, on 2.6 times the code).

What's missing is testing across the whole system: the browser smoke test only logs in and searches, so the main flow (request → accept → hold → notification) is only checked by hand, and the Stripe hold paths and startup wiring are weakly tested ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435), [#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436), [#437](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/437)). The overselling test also came after the fix instead of first. Sprint 3 change 3 adds an end-to-end test of the booking flow.

## Cross-team testing

We black-box tested **BisonRides** on their live site and filed three issues ([#96](https://github.com/BisonRIdes/Comp4350Project/issues/96), [#97](https://github.com/BisonRIdes/Comp4350Project/issues/97), [#98](https://github.com/BisonRIdes/Comp4350Project/issues/98)): a blank page for any unknown URL, no way to reset a forgotten password, and rides that show no price. None of these were crashes in the code they'd written; they were things a new user hits that the developers, who know where everything is, never do.

We found the same kind of problem on our own site when we tested the release with fresh eyes: admins had no link to the driver applications page ([#466](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/466), fixed before the deadline), a rider can't remove a card ([#464](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/464)), and the test card only takes a US postal code. **What we learned:** our automated tests check that features work the way we built them, but only using the site as a newcomer shows what's missing or confusing, so we'll do that on every release (below).

The feedback on GetDrove from the other team hadn't arrived by the deadline, and the instructor told us cross-team testing isn't required this iteration; we'll respond to it when it arrives.

## Process

- **Communication worked.** We talked through problems on Discord as they came up, and when one person's work blocked someone else's (an API contract before its implementation, saved cards before payment holds), we got it done early so everyone had time to finish theirs. Work came in on time.
- **Contract-first pull requests worked.** Changes that touched several services started with a pull request for the API contract, agreed before anyone built against it, so the services and the web app fit together when they met.
- **Reviews caught real bugs**, such as the geocoder throttle and cache ([#447](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/447)) and the demo data that couldn't seat a rider ([#460](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/460)), but large pull requests took several rounds.
- **The branching strategy cost us the most time** (see above): sync pull requests, broken syncs, and stories waiting on other stories.
- **Board hygiene slipped at the end of the sprint.** Some tasks were created without a label, milestone or parent, so they didn't show where they belonged on the board; we cleaned this up before the deadline.

## What we'll change for Sprint 3

1. **A simpler branching strategy: short-lived task branches straight from `develop`.** No more feature branch per story. Each task branches from `develop` and is squash-merged back into `develop` once it's reviewed and its checks pass, ideally within two or three days. A story is done when all its tasks are merged; the board, not a branch, tracks the story. A task must leave `develop` working: unfinished screens aren't linked from the app until the story is done. This removes the sync pull requests, and work that depends on another task only waits for that task, not a whole story. **Check at the next retro:** no `sync/*` pull requests, and task branches merged within three days. `docs/process/git-workflow.md` is updated before Sprint 3 work starts.
2. **Release early, and test every release as a newcomer.** Release to `main` as soon as a story is done, at least once a week, instead of once at the end. After each release, someone tries the new screens on the live site with the demo accounts before we tag it, and files what they find. **Check:** at least three releases in Sprint 3, none in the last 24 hours before the deadline.
3. **An end-to-end browser test of the booking flow.** Extend the smoke test to request a seat, accept it as the driver, and check the rider sees it accepted, so the most important path is tested across all the services on every release ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435)). **Check:** it runs in the Deploy workflow.

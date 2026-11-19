# Sprint 2 retro

> Back to [Sprint 2](../../sprint2.md) · Previous: [Sprint 1 retro](sprint1.md)

**Reviewed by:** <!-- who was there -->, <!-- date -->

<!-- TODO(#185): fill in at the retro meeting. The "Facts to discuss" lists are prepared from GitHub
so the meeting can start from data; the conclusions are the team's. Delete this comment and every
"Facts to discuss" list once the sections are written. -->

## Did we do what we said in Sprint 1?

The Sprint 1 retro ended with four changes. For each: did it happen, and did it help?

| Change we agreed | What happened | Keep? |
|---|---|---|
| 1. Every task gets a "done when" before it's assigned | | |
| 2. Acceptance-criteria tests go in the same PR as the feature | | |
| 3. Check the PR base and title, and run `scripts/check.sh`, before opening a PR | | |
| 4. Try each new screen as a first-time user on the live site | | |

## What we're proud of

- **GetDrove works end to end.** A student can sign up, add a card, find a ride by typing an address, request a seat, and get accepted, with their share held on their card and a notification at every step. A driver can post one-off or recurring trips, see what each request adds to their drive, and accept or decline. That flow runs across five services (Accounts, Trips, Routing, Payments, Notifications) that talk to each other through API calls and 14 kinds of events, on the live site.
- **Lots of features without breaking what was there.** We finished 12 stories this sprint, and parts of two more, and the 1,838 backend and 482 frontend tests, run on every pull request, kept the Sprint 1 features working. Coverage went up on the frontend and held on the backend, and the gaps we know about are written down ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435), [#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436), [#437](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/437)), not hidden.
- **The frontend looks good and is honest about its gaps.** The screens are consistent and work on a phone. When live testing found gaps (no admin link, no way to remove a card, a US-only postal box with the test card), we fixed what we could before the deadline ([#466](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/466)) and filed the rest for Sprint 3 ([#464](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/464)).
- **Decisions are written down.** Every significant choice this sprint has an ADR (0023 to 0027: approved drivers, seat counting, payment holds, releases, geocoding), so anyone can see why something was built the way it was.
- **CI/CD we can trust.** Every pull request runs the full checks; every merge to `develop` builds the images; a release to `main` reuses those exact images, deploys them, runs a smoke test against the live site, and posts to our Discord if anything fails. Dependabot ([#179](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/179)) now opens pull requests for outdated or vulnerable dependencies, and CodeQL scans the code for security problems.
- **Communication and timing.** We talked through problems on Discord as they came up, and when one person's work blocked someone else's (contracts before implementations, cards before payment holds), we got it done early enough that everyone had time to finish theirs. Work came in on time.

## What could have been better

<!-- One or two, with links, and what we'd do differently. -->

**Facts to discuss:**

- **Syncing feature branches.** Long-lived story branches (#8, #41, #46, #67, #150) needed several syncs of `develop` each (`sync/develop-into-*` PRs). One sync PR used `develop` itself as its head branch and had to be redone, and one sync broke two tests that passed on their own branch ([run](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/runs/44203058951)).
- **Review rounds.** Several pull requests needed two or more rounds of review before merging (for example #400, #403, #410, #419, #425, #427).
- **Release gate.** Payment holds (#67) reached `develop` before saved cards (#150), so `develop` couldn't be released to `main` until #150 was finished too.
- **CI.** 5 of the last 150 CI runs failed, and 12 were cancelled by a newer push; every failure was fixed on its branch before merging. All 33 Delivery runs on `develop` passed.

## How testing fit into our workflow

<!-- Compare with Sprint 1: did acceptance-criteria tests come with the feature this time? -->

**Facts to discuss:**

- The overselling test (#50) was written as its own task after the guarded update (#47), not first, as the implementation plan intended.
- One flaky frontend test was fixed rather than retried (#399).
- Coverage went up on the frontend (79% → 86.5%) and held on the backend (98% → 97%, on 2.6 times the code), but the browser, Stripe and startup-wiring gaps remain ([#435](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/435), [#436](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/436), [#437](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/437)).

## Cross-team testing

<!-- What we learned from testing another team's app, and from their feedback on ours (#183). -->

## Process

<!-- Git workflow, reviews, communication, how the work was split. -->

## What we'll change for Sprint 3

<!-- Three or four concrete changes, each one we can check at the next retro. -->

1.
2.
3.

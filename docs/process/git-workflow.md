# Git Workflow

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

We use **Git Flow**, with a feature branch for each user story. Nobody pushes directly to `main`, `develop` or a feature branch; every change reaches them through a pull request.

## Branches

| Branch | Created from | Merged into | Purpose |
|---|---|---|---|
| `main` | — | — | Released, stable code only. **Every merge deploys the live site.** Every commit on `main` is a tagged release. |
| `develop` | `main` (once) | — | Integration branch. Finished stories come together here. Every merge runs the full test suite and publishes deployable images (it does not change the live site). |
| `feature/*` | `develop` | `develop` | One branch per user story. The story's tasks are merged into it, and it's merged into `develop` once the story is done. Created by the GitHub Manager at the start of the sprint. |
| `task/*`, `fix/*`, etc. | the story's `feature/*` branch | the same `feature/*` branch | One branch per task or bug in a user story. |
| `task/*`, `docs/*`, etc. (not in a story) | `develop` | `develop` | Work that isn't part of a user story: CI, docs, process, sprint wrap-up. |
| `release/*` | `develop` | `main` **and** `develop` | Preparing a release: final bug fixes, version number, release notes. |
| `hotfix/*` | `main` | `main` **and** `develop` | Urgent fixes to released code that can't wait for the next release. |

`main` is the repository's default branch, so the repository page shows the latest release and the milestone submissions. Day-to-day work still happens on feature branches and `develop`, which means:

- **New pull requests target `main` by default.** When you open a pull request from a work branch, change the **base** branch to the branch you started from: the story's `feature/*` branch, or `develop` for work outside a story. Reviewers should check the base branch too.
- **`Closes #…` only closes the issue automatically when the change reaches `main`** (in the next release). After merging a work branch, close its issue yourself, or leave it to close with the release; the project board moves the card to Done when the pull request is merged either way.

## Branch names

Feature branches use the user story's issue number:

```
feature/<story-number>-<short-description>
```

```
feature/34-request-a-seat
feature/150-payment-card
```

Work branches use the task's issue number:

```
<type>/<issue-number>-<short-description>
```

```
task/140-trip-detail
fix/57-chat-access-after-removal
docs/12-api-readme
```

Types: `task`, `fix`, `refactor`, `test`, `docs`, `chore`. `feature/` is only for user story branches. A work branch is created from its story's feature branch, or from `develop` if the issue isn't part of a story.

Release and hotfix branches use the version number:

```
release/0.2.0
hotfix/0.2.1-seat-count-negative
```

## Versioning

We use [semantic versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- Each release increases the minor version: `v0.1.0`, `v0.2.0`, `v0.3.0`, and so on. A sprint may have more than one release.
- The release that closes each sprint is noted in that sprint's `sprintN.md`.
- A hotfix increases the patch version, e.g. `v0.2.0` → `v0.2.1`.
- Releases before the first sprint release (for example, deploying the walking skeleton) use `v0.0.x`.
- The final submitted version is `v1.0.0`.

## Working on a task (day to day)

Start from the story's feature branch (the issue says which story it's part of, e.g. "Part of #34"):

```bash
git fetch
git checkout -b task/140-trip-detail origin/feature/34-request-a-seat
# ...make changes...
git add .
git commit -m "feat(web): trip detail screen with pickup point and cost"
git push -u origin task/140-trip-detail
```

Open a pull request into `feature/34-request-a-seat` (change the base branch from the default `main`). Before doing so, bring your branch up to date with the feature branch and fix any conflicts:

```bash
git fetch
git checkout task/140-trip-detail
git merge origin/feature/34-request-a-seat
```

The pull request needs one approval and passing checks, like any other. Merge it with **Squash and merge**, so each task is one commit on the feature branch.

For work that isn't part of a story (CI, docs, process), do the same from `develop` instead: branch from `origin/develop` and open the pull request into `develop`.

## Keeping a feature branch up to date

Other stories reach `develop` while yours is in progress. Bring them into your feature branch regularly (at least twice a week) and always before the story is merged into `develop`, so conflicts are found early and in small pieces:

1. Open a pull request from `develop` into the feature branch.
2. Merge it with **Create a merge commit**. Never squash it: squashing copies `develop`'s changes in as one new commit, which conflicts with them again when the story goes back to `develop`.

The **Update branch** button on a pull request doesn't work for feature branches, because nobody can push to them directly.

## Finishing a story

When all of a story's tasks are merged into its feature branch:

1. Bring the feature branch up to date with `develop` (above).
2. The GitHub Manager opens a pull request from the feature branch into `develop`. It's reviewed like any other and the checks must pass.
3. Merge it with **Create a merge commit**, so each task's commit stays visible in `develop`'s history.
4. The GitHub Manager deletes the feature branch.

## Making a release

Releases are prepared and merged by the **GitHub Manager (Andrew)**, as set out in the [working agreement](working-agreement.md). `main` only ever receives tested release or hotfix branches, and **merging into `main` deploys the live site** (see [Deployment](#deployment-and-branches)).

**When to release:** at the end of every sprint at minimum, so the milestone submission is live. Release more often whenever a useful set of stories is finished on `develop`, and always before a demo meeting, so the live site shows current work.

1. Create the release branch from `develop`:
   ```bash
   git checkout develop && git pull
   git checkout -b release/0.2.0
   git push -u origin release/0.2.0
   ```
2. On the release branch, only bug fixes, version-number updates, and release notes are allowed. No new features; those wait for the next release. Work on feature branches continues as normal.
3. Open a pull request from `release/0.2.0` into `main`. After approval, merge it with **Create a merge commit**. This starts the deployment to the live site; check that the workflow and its smoke test pass.
4. Tag the release on `main` and push the tag:
   ```bash
   git checkout main && git pull
   git tag -a v0.2.0 -m "Release 0.2.0"
   git push origin v0.2.0
   ```
   Then create a GitHub Release from the tag with a short summary of what's included.
   If this release is a sprint submission, also tag it as described in [Milestone submission tags](#milestone-submission-tags).
5. Open a pull request from `release/0.2.0` into `develop`, so any fixes made during the release return to `develop`. Merge it with **Create a merge commit**.
6. Delete the release branch.

## Milestone submission tags

Each sprint submission is marked with a tag on `main`, named `sprint-0`, `sprint-1`, `sprint-2`, and so on. Files like `README.md` and the docs keep changing in later sprints, so the tag is how the marker (and we) can see exactly what was submitted for each milestone.

- The tag points at the commit on `main` that was submitted. For sprints with a release, that is the release's merge commit, so it carries both tags (for example `v0.2.0` and `sprint-1`).
- The GitHub Manager creates it through **Releases → Draft a new release**: type the new tag name (`sprint-N`), set the target to `main`, title it `Sprint N: <short summary>`, and list what was submitted. Or from the command line:
  ```bash
  git checkout main && git pull
  git tag -a sprint-1 -m "Sprint 1 submission"
  git push origin sprint-1
  ```
- Tags are never moved or deleted once the submission deadline has passed. If something has to change after submission, it goes in the next release.
- `sprintN.md` links to its tag, e.g. `https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/tree/sprint-1`.

`sprint-0` marks the Sprint 0 planning submission.

## Hotfixes

Used only for serious problems in released code (for example, something broken in a version we're demoing).

1. Create the branch from `main`:
   ```bash
   git checkout main && git pull
   git checkout -b hotfix/0.2.1-seat-count-negative
   ```
2. Fix the problem and open a pull request into `main`. After approval, merge with **Create a merge commit**, which deploys the fix to the live site.
3. Tag the new version (`v0.2.1`) on `main` as in the release steps.
4. Open a pull request from the hotfix branch into `develop` so the fix isn't lost, then merge it.
5. Delete the hotfix branch.

If a release branch is open at the time, merge the hotfix into the release branch instead of `develop`; it reaches `develop` when the release is merged back.

## Deployment and branches

We run **one live environment**, and it tracks **`main`** ([ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md)):

```
task branches ──PR──▶ feature branch (one per story)
                            │
                           PR
                            ▼
                         develop ──▶ CI + build images (tagged by commit) ──▶ GitHub Container Registry
                            │
                     release branch
                            │
                            ▼
                          main ──▶ deploy to the live site + smoke test
                            │
                       tag vX.Y.Z ──▶ versioned images on DockerHub (planned for Sprint 3, #189)
```

- **Pull requests into a feature branch** run the same checks as pull requests into `develop`.

- **`develop` (continuous delivery):** every merge runs the full test suite and builds and publishes deployable images. Nothing reaches the live site yet.
- **`main` (continuous deployment):** every merge (a release or hotfix) deploys to the live site automatically and runs a smoke test. A failed smoke test marks the workflow red and alerts the team in Discord.
- **The live site always matches a release on `main`**, so the instructor only ever sees reviewed, released code.
- **Rolling back:** if a release breaks the live site, redeploy the previous release tag's images, then fix with a hotfix.
- **Hotfixes** are merged into `main` (which deploys them) and then into `develop`.
- **`main` is the default branch**, but day-to-day work happens on feature branches and `develop`. Each sprint's submission is released to `main` and tagged `sprint-N`, so both branches match at every milestone.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<area>): <what changed, in the present tense>
```

Examples:

```
feat(routing): store computed route when a trip is posted
fix(requests): prevent seat count from going below zero
test(requests): simulate concurrent requests for the last seat
```

Keep commits focused on one change. Don't commit commented-out code, debugging output, or generated files.

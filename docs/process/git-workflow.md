# Git Workflow

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

We use **Git Flow**. Nobody pushes directly to `main` or `develop`; every change reaches them through a pull request.

## Branches

| Branch | Created from | Merged into | Purpose |
|---|---|---|---|
| `main` | — | — | Released, stable code only. Every commit on `main` is a tagged release. |
| `develop` | `main` (once) | — | Integration branch. Finished work comes together here. |
| `feature/*`, `fix/*`, etc. | `develop` | `develop` | One branch per issue or task. |
| `release/*` | `develop` | `main` **and** `develop` | Preparing a release: final bug fixes, version number, release notes. |
| `hotfix/*` | `main` | `main` **and** `develop` | Urgent fixes to released code that can't wait for the next release. |

`develop` is the repository's default branch, so new pull requests target it automatically.

## Branch names

Work branches:

```
<type>/<issue-number>-<short-description>
```

```
feature/4-signup-endpoint
fix/57-chat-access-after-removal
docs/12-api-readme
```

Types: `feature`, `fix`, `refactor`, `test`, `docs`, `chore`. All of them are created from `develop`.

Release and hotfix branches use the version number:

```
release/0.2.0
hotfix/0.2.1-seat-count-negative
```

## Versioning

We use [semantic versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- Each iteration's release increases the minor version: `v0.1.0`, `v0.2.0`, `v0.3.0`, and so on.
- A hotfix increases the patch version, e.g. `v0.2.0` → `v0.2.1`.
- The final submitted version is `v1.0.0`.

## Feature work (day to day)

```bash
git checkout develop
git pull
git checkout -b feature/4-signup-endpoint
# ...make changes...
git add .
git commit -m "feat(accounts): validate UofM email domain on signup"
git push -u origin feature/4-signup-endpoint
```

Open a pull request into `develop`. Before doing so, bring your branch up to date and fix any conflicts:

```bash
git checkout develop && git pull
git checkout feature/4-signup-endpoint
git merge develop
```

## Making a release (end of each iteration)

Releases are prepared and merged by the **GitHub Manager (Andrew)**, as set out in the [working agreement](working-agreement.md). Merging into `main` triggers the automatic deployment in GitHub Actions, so `main` only ever receives tested release or hotfix branches.

1. Create the release branch from `develop`:
   ```bash
   git checkout develop && git pull
   git checkout -b release/0.2.0
   git push -u origin release/0.2.0
   ```
2. On the release branch, only bug fixes, version-number updates, and release notes are allowed. No new features; those wait for the next release. Feature work continues on `develop` as normal.
3. Open a pull request from `release/0.2.0` into `main`. After approval, merge it with **Create a merge commit**.
4. Tag the release on `main` and push the tag:
   ```bash
   git checkout main && git pull
   git tag -a v0.2.0 -m "Release 0.2.0"
   git push origin v0.2.0
   ```
   Then create a GitHub Release from the tag with a short summary of what's included.
5. Open a pull request from `release/0.2.0` into `develop`, so any fixes made during the release return to `develop`. Merge it with **Create a merge commit**.
6. Delete the release branch.

## Hotfixes

Used only for serious problems in released code (for example, something broken in a version we're demoing).

1. Create the branch from `main`:
   ```bash
   git checkout main && git pull
   git checkout -b hotfix/0.2.1-seat-count-negative
   ```
2. Fix the problem and open a pull request into `main`. After approval, merge with **Create a merge commit**.
3. Tag the new version (`v0.2.1`) on `main` as in the release steps.
4. Open a pull request from the hotfix branch into `develop` so the fix isn't lost, then merge it.
5. Delete the hotfix branch.

If a release branch is open at the time, merge the hotfix into the release branch instead of `develop`; it reaches `develop` when the release is merged back.

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

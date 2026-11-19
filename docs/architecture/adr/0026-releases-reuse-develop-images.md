# ADR 0026: Releases deploy the images already built and tested on develop

- **Status:** Proposed
- **Date:** 2026-11-18
- **Amends:** [ADR 0016](0016-google-cloud-hosting-and-deploy-from-main.md) (how a release gets its images)

## Context

[ADR 0016](0016-google-cloud-hosting-and-deploy-from-main.md) set up continuous delivery on `develop` (every merge runs the checks and publishes the images to GitHub Container Registry) and deployment from `main`. In Sprint 1, the Deploy workflow built all eight images again for the release commit. That meant:

- What went live wasn't byte for byte what had passed the checks on `develop`: a base image or dependency could change between the two builds.
- Each release spent several minutes rebuilding, including the OSRM images with the Winnipeg map.

A release merges `develop` into `main` with a merge commit, so the release commit has exactly the same files as the `develop` commit it came from, whose images Delivery already published.

## Options considered

- **Keep building on `main`:** simple, but the two problems above.
- **Deploy by `develop`'s commit SHA:** no rebuild, but every live version would be tagged with a commit that isn't on `main`, which makes rollback and the release history confusing.
- **Re-tag `develop`'s images with the release commit's SHA:** the registry adds a tag to the existing image; nothing is rebuilt or downloaded.

## Decision

**The Deploy workflow reuses `develop`'s images** (#177). Its first job checks that the release commit has the same files as its `develop` parent and that all eight images were published for that parent, then adds the release commit's SHA as a tag to those images. The deploy pulls them by that tag. It **builds only when there's nothing to reuse**: a hotfix committed to `main`, a release merged before Delivery finished, or a run that refreshes the map. The run's summary says which happened.

After deploying, the workflow checks the live site: every `/health`, a real OSRM route, and a Playwright browser test in which a demo rider logs in and searches. A failure in any step posts to Discord.

## Consequences

**Positive**

- What goes live is exactly what passed every check on `develop`.
- A release deploys in a few minutes.
- Every live version is still tagged with a commit on `main`, so rolling back is running Deploy with an earlier release's SHA, as before.

**Negative / trade-offs**

- The deploy depends on Delivery having finished for the `develop` commit; if it hasn't, the workflow falls back to building, which is slower but still correct.
- The check that the files match must be right, or a release could deploy images for different code. It compares the trees of the two commits, which Git guarantees.
- Images published for `develop` must be kept as long as a release might roll back to them. GitHub Container Registry keeps them until they're deleted.

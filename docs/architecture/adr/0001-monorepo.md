# ADR 0001: Monorepo for all code and documentation

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

We need one place for five backend services, the frontend, shared libraries, contracts, infrastructure, and documentation. Our issues, project board, labels, docs, Git Flow, and branch protection already live in one GitHub repository.

## Options considered

- **Monorepo:** One repo; shared code as Gradle subprojects; one CI workflow with path filters.
- **Polyrepo:** One repo per service; shared code published as packages; one pipeline per repo.

## Decision

Use a **monorepo**.

## Consequences

**Positive**

- A cross-service change (e.g. a new event) is one PR covering producer, consumer, and contract.
- Shared libraries (auth, events, errors) are plain Gradle subprojects, with no package publishing.
- One place for the instructor and teammates to look.

**Negative / trade-offs**

- CI must use path filters so unrelated services don't build on every PR.
- Less independence per service; acceptable for a 6-person team releasing once per sprint.

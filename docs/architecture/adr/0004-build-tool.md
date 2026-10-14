# ADR 0004: Gradle as the build tool

- **Status:** Superseded by [ADR 0017](0017-python-fastapi-backend.md)
- **Date:** 2026-10-04

> **Superseded.** With the move to Python, the monorepo is managed by a **uv workspace** (one `uv.lock`, packages built with `uv_build`), not Gradle. See [ADR 0017](0017-python-fastapi-backend.md) and [Monorepo structure](../monorepo.md). This record is kept for history.

## Context

The monorepo contains five services and shared libraries that need consistent dependency versions and fast builds in CI.

## Options considered

- **Gradle (Kotlin DSL):** Multi-project builds, a shared version catalog, incremental builds and caching.
- **Maven:** Simpler, declarative XML; multi-module works with more repetition.

## Decision

Use **Gradle** with the Kotlin DSL and a shared version catalog (`gradle/libs.versions.toml`).

## Consequences

**Positive**

- One place defines every dependency version for all services.
- Faster incremental builds and good GitHub Actions caching.

**Negative / trade-offs**

- Build files are code, which has a learning curve for teammates new to Gradle.

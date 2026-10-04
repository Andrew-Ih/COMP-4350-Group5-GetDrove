# ADR 0004: Gradle as the build tool

- **Status:** Accepted
- **Date:** 2026-10-04

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

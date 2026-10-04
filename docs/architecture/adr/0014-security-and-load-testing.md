# ADR 0014: CodeQL, Trivy, Dependabot, and JMeter

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

Sprint 3 requires an automated security/static-analysis tool in the pipeline with findings handled, and load testing at a baseline of 20 concurrent users and 200 requests per minute.

## Options considered

- **Security:** CodeQL, Trivy, Dependabot, SonarCloud, Semgrep.
- **Load testing:** JMeter (course default), k6, Gatling.

## Decision

Use **CodeQL** (code scanning), **Trivy** (image and dependency scanning), and **Dependabot** (dependency updates): Dependabot from Sprint 1, CodeQL from Sprint 2, Trivy with DockerHub publishing in Sprint 3. Use **JMeter** for load testing.

## Consequences

**Positive**

- Code, dependencies, and container images are all covered, inside GitHub, free for public repos.
- JMeter is the course default, so results need no tool justification.

**Negative / trade-offs**

- JMeter test plans are XML and clunky to edit by hand.

# ADR 0013: Testing, contract, and code-quality tools

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

Every sprint is graded on testing evidence (unit, integration, regression, coverage). Five services and a frontend must stay compatible, and code style must be consistent across six developers.

## Options considered

- **Backend:** JUnit 5, Mockito, AssertJ, Testcontainers, WireMock, stripe-mock, ArchUnit, JaCoCo.
- **Frontend:** Vitest + React Testing Library + MSW vs Jest; Playwright vs Cypress for end-to-end.
- **Contracts:** OpenAPI + JSON Schema validation vs Pact vs Spring Cloud Contract.
- **Formatting/linting:** Spotless (google-java-format) + Checkstyle; Prettier + ESLint.

## Decision

Backend: **JUnit 5, Mockito, AssertJ, Testcontainers, WireMock, stripe-mock, ArchUnit, JaCoCo**. Frontend: **Vitest, React Testing Library, MSW**, and **Playwright** for end-to-end. Contracts: **OpenAPI specs and JSON Schemas validated in tests**, with frontend types generated from the specs. Formatting and linting: **Spotless (google-java-format) + Checkstyle** for Java, **Prettier + ESLint** for TypeScript, all enforced in CI.

## Consequences

**Positive**

- Real PostgreSQL and Redis in integration tests (Testcontainers), including the seat concurrency test.
- Screens can be built and tested against mocked APIs before endpoints exist (MSW).
- Contract drift fails CI instead of failing in production.

**Negative / trade-offs**

- Contract checks are lighter than Pact; acceptable at our team size.

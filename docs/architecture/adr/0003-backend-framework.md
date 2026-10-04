# ADR 0003: Java 21 + Spring Boot 3 for all backend services

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The backend has five services with real complexity: concurrency (seat booking), payments, event-driven messaging, scheduled jobs, and authorized WebSockets. The services must agree on contracts, and we want Clean Architecture enforced across six developers. Most of the team knows Java from coursework.

## Options considered

- **Java 21 + Spring Boot 3:** Static typing, dependency injection, built-in JWT validation, STOMP WebSockets, transactions, schedulers; ArchUnit and Testcontainers for structure and testing.
- **Python + FastAPI:** Fully object-oriented and capable, less code, automatic OpenAPI docs; structure and typing rely more on discipline.
- **A mix:** Different frameworks per service.

## Decision

Use **Java 21 with Spring Boot 3** for all five services, with Spring Data JPA, Flyway, Spring Security (OAuth2 resource server), springdoc OpenAPI, and Spring's STOMP support. PostgreSQL with PostGIS, one schema and one database user per service.

## Consequences

**Positive**

- The compiler catches broken contracts and ports across services.
- Clean Architecture layers can be enforced with ArchUnit tests.
- The hard parts (JWT, WebSockets, transactions, scheduling) are built into the framework.
- Matches the team's existing Java experience.

**Negative / trade-offs**

- More boilerplate than Python.
- Each service uses more memory; JVM heap is capped (about 256–400 MB per service) to fit the VM.

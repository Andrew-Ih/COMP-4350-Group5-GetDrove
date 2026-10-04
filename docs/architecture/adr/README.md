# Architecture Decision Records

> Back to [Technology stack](../tech-stack.md) · [Architecture](../architecture.md) · [README](../../../README.md)

An Architecture Decision Record (ADR) is a short document that records one significant technical decision: the context, the options we considered, what we chose, and the consequences.

**How we use them**

- One ADR per significant decision, numbered in order. Copy an existing ADR as a template.
- New ADRs start as **Proposed**. They become **Accepted** when the team approves the PR that adds them.
- We don't rewrite accepted ADRs. If a decision changes, we add a new ADR that **supersedes** the old one and mark the old one **Superseded by ADR XXXX**.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-monorepo.md) | Monorepo for all code and documentation | Accepted |
| [0002](0002-frontend-framework.md) | Next.js + TypeScript for the frontend | Accepted |
| [0003](0003-backend-framework.md) | Java 21 + Spring Boot 3 for all backend services | Accepted |
| [0004](0004-build-tool.md) | Gradle as the build tool | Accepted |
| [0005](0005-message-broker.md) | Redis Streams as the message broker | Accepted |
| [0006](0006-gateway-and-authentication.md) | Traefik as the gateway; JWTs validated in each service | Accepted |
| [0007](0007-hosting-and-environments.md) | Oracle Cloud Always Free VM, one live environment from develop | Accepted |
| [0008](0008-routing-engine.md) | OSRM as the routing engine | Accepted |
| [0009](0009-maps.md) | MapLibre GL JS with OpenFreeMap tiles | Accepted |
| [0010](0010-email.md) | Mailpit locally, Brevo in production | Accepted |
| [0011](0011-document-storage.md) | Docker volume for driver documents | Accepted |
| [0012](0012-pricing-and-no-shows.md) | Per-km pricing and a 100% no-show charge | Accepted |
| [0013](0013-testing.md) | Testing, contract, and code-quality tools | Accepted |
| [0014](0014-security-and-load-testing.md) | CodeQL, Trivy, Dependabot, and JMeter | Accepted |
| [0015](0015-driver-approval.md) | Minimal admin page for driver approval | Accepted |

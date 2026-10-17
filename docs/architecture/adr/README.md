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
| [0003](0003-backend-framework.md) | Java 21 + Spring Boot 3 for all backend services | Superseded by 0017 |
| [0004](0004-build-tool.md) | Gradle as the build tool | Superseded by 0017 |
| [0005](0005-message-broker.md) | Redis Streams as the message broker | Accepted |
| [0006](0006-gateway-and-authentication.md) | Traefik as the gateway; JWTs validated in each service | Accepted (Python implementation in 0017) |
| [0007](0007-hosting-and-environments.md) | Oracle Cloud Always Free VM, one live environment from develop | Superseded by 0016 |
| [0008](0008-routing-engine.md) | OSRM as the routing engine | Accepted |
| [0009](0009-maps.md) | MapLibre GL JS with OpenFreeMap tiles | Accepted |
| [0010](0010-email.md) | Mailpit locally, Brevo in production | Accepted |
| [0011](0011-document-storage.md) | Docker volume for driver documents | Accepted |
| [0012](0012-pricing-and-no-shows.md) | Per-km pricing and a 100% no-show charge | Accepted |
| [0013](0013-testing.md) | Testing, contract, and code-quality tools | Accepted (backend tools superseded by 0017) |
| [0014](0014-security-and-load-testing.md) | CodeQL, Trivy, Dependabot, and JMeter | Accepted |
| [0015](0015-driver-approval.md) | Minimal admin page for driver approval | Accepted |
| [0016](0016-google-cloud-hosting-and-deploy-from-main.md) | Google Cloud VM, live site deployed from main | Accepted |
| [0017](0017-python-fastapi-backend.md) | Python 3.13 + FastAPI for all backend services | Accepted (realtime amended by 0018, logging by 0019) |
| [0018](0018-live-tracking-as-stretch-goal.md) | Live tracking as a stretch goal; polling instead of WebSockets | Accepted |
| [0019](0019-standard-library-logging.md) | Python's standard logging instead of structlog | Accepted |
| [0020](0020-password-hashing.md) | Argon2id (`argon2-cffi`) for password hashing | Accepted |
| [0021](0021-verification-email-requested-event.md) | A separate `VerificationEmailRequested` event for resends | Accepted |
| [0022](0022-login-sessions.md) | Login sessions: 15-minute access token in memory, rotating HttpOnly refresh cookie with reuse detection | Proposed |

# ADR 0006: Traefik as the gateway; JWTs validated in each service

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The browser needs one public entry point with HTTPS, routing to five services, the Next.js server, and WebSockets. Every protected endpoint must validate the user's identity.

## Options considered

- **Traefik:** Configured with Docker labels, automatic Let's Encrypt HTTPS, native WebSocket support, no code.
- **Spring Cloud Gateway:** A Java gateway service with custom filters; another service to build and deploy.
- **nginx / Caddy:** Simple reverse proxies configured by file.
- **Validate JWTs at the gateway (ForwardAuth):** Every request checked by Accounts before routing.
- **Validate JWTs in each service:** Each service checks tokens with Accounts' public key.

## Decision

Use **Traefik** for routing and HTTPS only. **Accounts issues RS256 JWTs**, and **each service validates them itself** with Spring Security's resource server, using Accounts' JWKS endpoint, configured once in `libs/common-security`. Internal `/internal/…` endpoints are never routed by Traefik.

## Consequences

**Positive**

- No auth code in the gateway; HTTPS certificates renew automatically.
- Services are protected even if a gateway route is misconfigured, and auth works identically locally and in tests.
- No extra network hop to Accounts on every request.

**Negative / trade-offs**

- Every service must include `common-security`; a mistake there affects all services, so it gets thorough tests.

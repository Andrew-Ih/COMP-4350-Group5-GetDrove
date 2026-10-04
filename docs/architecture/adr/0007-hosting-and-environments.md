# ADR 0007: Oracle Cloud Always Free VM, one live environment from develop

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

We need a live deployment every sprint at no cost and with low maintenance. The stack (5 services, PostgreSQL/PostGIS, Redis, two OSRM instances, Traefik, Next.js) needs about 4 GB of RAM and several always-running processes (outbox relays, consumers, schedulers, WebSockets), which rules out scale-to-zero serverless platforms without a redesign. Sprint 2 requires deployment on changes to the main development branch; Sprint 3 requires images on DockerHub.

## Options considered

- **Oracle Cloud Always Free VM:** Free indefinitely; large ARM VM; signup and capacity not guaranteed; idle reclaim policy.
- **AWS Free plan:** Up to $200 credits for up to 6 months; cannot be charged; credit limits VM size.
- **Serverless free tiers (Cloud Run, Vercel, Neon, Upstash, …):** No server to manage; requires replacing Redis Streams, OSRM, schedulers, and WebSockets; many accounts and quotas.
- **Paid VPS (e.g. Hetzner):** Cheap and reliable; not free.
- **Two environments (staging + production):** More realistic; doubles resources and release work.

## Decision

Host on an **Oracle Cloud Always Free VM** (VM.Standard.A1.Flex, **2 OCPU / 12 GB**, Ubuntu 24.04 LTS ARM64, Canadian home region) running **Docker Compose**. **Backup:** the **AWS Free plan** with a t4g.large if Oracle signup or capacity fails. Run **one live environment deployed automatically from `develop`**; `main` holds tagged releases (`v0.1.0`, `v0.2.0`, `v1.0.0`) that publish versioned images to DockerHub.

## Consequences

**Positive**

- $0 cost; local and live environments are identical (Docker Compose).
- Low maintenance: GitHub Actions builds `linux/arm64` images and deploys on every merge to `develop`.
- The live site always matches the current development branch, as the course requires.

**Negative / trade-offs**

- We maintain one server (OS updates, disk, backups).
- ARM images are required; OSRM's ARM support must be confirmed in the Sprint 1 spike.
- Idle instances may be reclaimed; upgrading the account to pay-as-you-go (with a $1 budget alert) avoids this.

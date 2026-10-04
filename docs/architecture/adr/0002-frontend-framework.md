# ADR 0002: Next.js + TypeScript for the frontend

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The web app must be mobile-first, match our mockups, show live maps, and talk to five backend services. It's built incrementally, screen by screen, alongside the backend stories.

## Options considered

- **Next.js + TypeScript:** React framework with file-based routing (App Router), server rendering where useful, and a production server.
- **Vite + React + TypeScript:** A plain React single-page app with a separate router.

## Decision

Use **Next.js with TypeScript**, App Router. Next.js is the frontend only: business logic stays in the Spring Boot services.

## Consequences

**Positive**

- Route folders map directly onto the mockup URLs (`/ride/results`, `/drive/new`, …).
- Server rendering for the sign-up and public share pages; client components for maps, live data, and forms.
- TypeScript types are generated from the backend OpenAPI specs.

**Negative / trade-offs**

- Map components must be loaded client-side only (`next/dynamic` with `ssr: false`).
- A Node server runs in production instead of static files, in its own container.

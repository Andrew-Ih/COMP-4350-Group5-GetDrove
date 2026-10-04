# ADR 0015: Minimal admin page for driver approval

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

Drivers can't post trips until their licence and insurance are approved. Someone has to review and approve or reject them, and the instructor should be able to see the flow.

## Options considered

- **Minimal admin page + seeded admin:** A list of pending drivers with document links and approve/reject.
- **API or database only:** No UI; demos look unfinished.
- **Auto-approve:** Fastest; makes approval statuses meaningless and fails the acceptance criteria.

## Decision

Build a **minimal admin page** listing pending drivers with approve and reject (with a reason), and create **one admin account** in the seed script. Admin credentials are included in sprint2.md and sprint3.md for the instructor.

## Consequences

**Positive**

- A complete, demonstrable approval workflow with little extra code.

**Negative / trade-offs**

- The admin account must be protected: strong password, and admin role checked on every admin endpoint.

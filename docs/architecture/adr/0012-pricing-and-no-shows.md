# ADR 0012: Per-km pricing and a 100% no-show charge

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The rider's cost must be shown before requesting, proportional to the distance they ride, and equal to what's charged unless the trip changes. A rider marked as a no-show must be charged according to a defined policy.

## Options considered

- **Per-km rate × rider distance:** Fixed, predictable price that doesn't change as others join.
- **Share of the trip's total cost:** Riders split the trip cost; prices change as riders join or leave.
- **No-show: 100% / 50% / flat fee:** Trade-off between driver compensation and leniency.

## Decision

Rider's share = rider distance × **$0.45/km**, rounded to the nearest 5¢, with a **$2.00 minimum**. A no-show rider is charged **100%** of their quoted share. The rate, minimum, and no-show percentage are configuration values.

## Consequences

**Positive**

- The quoted price never changes because of other riders, matching the acceptance criteria.
- A one-line explanation is easy ("9.2 km × $0.45/km").
- Drivers are fully compensated for no-shows, which supports driver supply.

**Negative / trade-offs**

- Riders don't get cheaper when more people join; acceptable for simplicity and predictability.

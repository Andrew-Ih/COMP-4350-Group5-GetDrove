# ADR 0023: Trips keeps its own list of approved drivers, from Accounts' events

- **Status:** Proposed
- **Date:** 2026-11-15

## Context

Only approved drivers can post trips ([#8](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/8), [#11](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/11)). Approval is decided in Accounts, where admins review drivers' documents ([ADR 0015](0015-driver-approval.md), #127), but the check happens in Trips, on every `POST /api/trips`. #8 also asks that approval takes effect straight away, without logging out and back in. Each service owns its own data and no service reads another's tables ([ADR 0017](0017-python-fastapi-backend.md)), so Trips needs another way to know who is approved.

## Options considered

- **A claim in the access token** (`roles: ["user", "driver"]`): no extra calls or tables, but the token is only re-issued at login or refresh (up to 15 minutes, [ADR 0022](0022-login-sessions.md)), so a newly approved driver would be refused until then, and a rejected one allowed. That breaks #8's acceptance criteria.
- **Trips asks Accounts on every post** (an internal HTTP call): always current, but posting fails whenever Accounts is down or slow, adds a network call to every post, and ties the two services' uptime together.
- **Trips keeps its own copy, updated from events:** Accounts already publishes `DriverApproved` and `DriverRejected` through the outbox (#127). Trips consumes them from `events.accounts` and keeps an `approved_drivers` table; posting reads it locally.

## Decision

**Trips keeps an `approved_drivers` table (a read model)**, filled by consuming `DriverApproved` and emptied by `DriverRejected`, with `libs/events`' `StreamConsumer` (consumer group `trips`). Each event is recorded in `trips.processed_events` in the same transaction as the change, so a repeat delivery changes nothing twice. `POST /api/trips` checks the table first and answers `403 driver_not_approved` if the driver isn't on it.

## Consequences

**Positive**

- Approval takes effect within about a second of the admin's decision, in the driver's current session.
- Posting doesn't depend on Accounts being up, and costs one indexed lookup instead of an HTTP call.
- It's the pattern for later copies of another service's data, e.g. Notifications' `trip_members` (#146).

**Negative / trade-offs**

- Eventually consistent: for the moment between the admin's decision and Trips handling the event, the old status applies. If Redis or the consumer is down, approvals wait in the stream until it's back (the service logs an error if the consumer stops).
- Anyone approved before Trips starts consuming is picked up on first start, because a new consumer group reads the stream from the beginning. If the stream were ever trimmed or lost, the list would need rebuilding from Accounts (a one-off script; not needed now).
- Demo and test drivers must be approved through Accounts (or its seed) so that the event reaches Trips; inserting into Trips' table directly is only for tests.

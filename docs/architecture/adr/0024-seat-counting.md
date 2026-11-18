# ADR 0024: Seats are taken with one guarded database update

- **Status:** Proposed
- **Date:** 2026-11-18

## Context

A trip has a few seats, and several things can try to take the last one at the same moment: a driver accepting two requests in two tabs, two co-drivers' clicks, or auto-accept accepting a new request while the driver accepts another by hand ([#41](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/41)). Story [#46](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/46) requires that exactly one wins, the others get a clear message, the count never drops below zero, and a cancelled or declined seat comes back at once. Trips runs more than one worker process, so anything held only in memory doesn't protect anything.

Accepting also places the rider's pickup in the trip's pickup order, which depends on the pickups already accepted, so two accepts on one trip mustn't interleave there either.

## Options considered

- **Read the count, check it in Python, then write it:** the classic race. Two transactions both read "1 seat left" and both write 0.
- **Serializable isolation for the whole service:** correct, but every conflicting transaction fails with a serialization error that has to be retried, including ones that don't touch seats, and the retries are easy to get wrong.
- **A Redis lock or counter in front of the database:** one more thing that can be out of step with the database, and a lock that can expire while a slow transaction still runs.
- **Let the database decide in one statement:** `UPDATE trips SET seats_available = seats_available - 1 WHERE id = :trip AND seats_available > 0 AND status = 'scheduled'`. PostgreSQL row-locks the trip while updating, so concurrent updates queue, and the second sees the first one's result. Zero rows updated means no seat was left.

## Decision

**Taking a seat is one guarded `UPDATE` (`take_seat`)**, in the same transaction as the request's status change and the `RequestAccepted` outbox row. If it updates no row, the transaction rolls back and the API answers `409 seat_taken`. Giving a seat back (`release_seat`) is the mirror image, guarded so it never goes above `seats_total`. A `CHECK (seats_available >= 0 AND seats_available <= seats_total)` constraint on the table backs both up.

Accept, decline and cancel also **lock the trip row first** (`SELECT … FOR UPDATE`), so changes to one trip's pickup order happen one at a time, and always in the same order (trip, then request), so they can't deadlock each other. Auto-accept goes through the same `take_seat`.

The guarantee is tested on real PostgreSQL with 20 concurrent accepts for one seat and for three, auto-accept racing a manual accept, and a cancelled seat taken straight away ([`test_seat_oversell.py`](../../../services/trips/tests/concurrency/test_seat_oversell.py), #50).

## Consequences

**Positive**

- Correct under any number of workers and requests, with no retry loop and nothing outside the database to keep in step.
- The losing request gets a specific, user-facing answer (`seat_taken`) instead of a generic error.
- The seat count, the request's status and the event always change together or not at all.

**Negative / trade-offs**

- Accepts on the same trip run one after another while the row is locked. A trip has at most 6 seats, so this is never a real queue.
- The lock is held while Trips asks Routing for the pickup order, so a slow Routing slows other accepts on that trip (not on other trips). Routing calls have a timeout, and if Routing doesn't answer, the pickup keeps the position worked out when the rider asked.
- The rule lives partly in SQL, so it's tested with integration tests against PostgreSQL, not only unit tests with fakes.

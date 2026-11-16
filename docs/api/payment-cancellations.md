# Release holds on cancellation (#72)

## Scope

Consumes the existing RequestDeclined, RequestCancelled and TripCancelled contracts.
Uncaptured PaymentIntents are cancelled, holds become RELEASED, and PaymentReleased is
published once through the transactional outbox. Scheduled holds that never reached
Stripe are retired without a provider call. No new public API or event fields are added.

Despite the issue title "Refund on cancellation", its acceptance criteria concern releasing
uncaptured holds. This task does not introduce refunds of captured payments. A captured or
uncertain payment is paused for reconciliation and is never falsely reported as released.
The capture-on-completion feature remains #71; extended reconciliation remains #153.

## Processing

Cancellation consumption durably records a tombstone and requests release. Request-level
cancellation verifies the stored request/trip/rider/driver identity. Trip cancellation marks
all recorded holds for that trip, not just the riders listed in its event.

The hold worker locks the row, retrieves the current Stripe intent, and cancels it with
release:<request-id>. An already-cancelled intent needs no second cancel call. State and
PaymentReleased commit together. Transient failures retry after 30s; mismatched, captured
or uncertain provider responses pause for reconciliation without a success event.

Tombstones prevent a delayed RequestAccepted from resurrecting a cancelled ride. Scheduling
and cancellation take the same per-trip advisory lock before row locks, so trip cancellation
cannot miss a concurrently inserted acceptance. Workers retain their row lock while resolving
provider state; acceptance, release and capture therefore cannot act concurrently on one row.

If authorization succeeded before its database commit failed, release recovers the same
PaymentIntent using the committed card/amount and original hold:<request-id> key before
cancelling it. This can briefly authorize and immediately cancel a prepared request when its
previous provider outcome was unknown. It never captures a payment. An unattempted schedule
has no such recovery call. Attempts beyond the conservative 23-hour idempotency window need
operator reconciliation rather than a blind new authorization.

A release request blocks further prepare/authorize/capture. Duplicate events never reset a
completed release or restart an intentionally paused reconciliation. If cancellation succeeds
but its DB transaction fails, a retry retrieves the cancelled intent and records one outcome.

## Database migration

Migration a72000000001 follows #70's a70000000001. It adds release_requested to payment_holds
and creates cancelled_requests and cancelled_trips in the Payments schema.

From the repository root, against a database already compatible with the #67 migration chain:

```powershell
uv run --package payments alembic -c services/payments/alembic.ini upgrade head
```

Tests use disposable PostgreSQL and Redis containers and never migrate the developer database.
The separate #151 migration must not be copied into this branch to apply this migration.

## Test

```powershell
uv run pytest services/payments -rs
uv run ruff format --check services/payments
uv run ruff check services/payments
uv run mypy services/payments/src
Push-Location services/payments
uv run lint-imports
Pop-Location
```

The suite covers every event, duplicates, whole-trip cancellation, scheduled work, late and
concurrent acceptance, provider timeouts, cancellation/capture exclusion, and DB failures after
provider authorization or cancellation. SDK tests cover retrieval error translation.

For explicit real Stripe verification, with Docker and a sandbox test key configured:

```powershell
$env:RUN_STRIPE_SANDBOX_HOLD="1"
uv run pytest services/payments/tests/test_stripe_sandbox_hold.py -q -s
Remove-Item Env:RUN_STRIPE_SANDBOX_HOLD
```

This opt-in test has three cases, one for each cancellation event. Each creates a dedicated
sandbox customer/card and a 625-cent CAD uncaptured hold, publishes cancellation, verifies
Stripe status canceled and zero amount received, and checks one PaymentReleased. It also
replays events to test idempotency. Failed tests attempt to cancel any remaining authorization
in cleanup. The ordinary suite skips these real API cases.

The seeded per-rider references from #70 are used. No #151 customer/card endpoints are merged.


## Verification recorded on 2026-11-15

- Automated Payments suite: 122 passed; 3 opt-in sandbox cases skipped by default.
- Real Stripe sandbox suite: all 3 cases passed. Each intent was canceled with zero captured.
  - Rider cancellation: pi_3UcFy2IQXqskkTT20vqxfYiT.
  - Driver decline: pi_3UcFyAIQXqskkTT20i0kmV7R.
  - Trip cancellation: pi_3UcFyHIQXqskkTT21PLeYiW9.
- Duplicate events produced one PaymentReleased per request.
- Formatting, lint, strict types and both architecture contracts passed.
- An initial sandbox run encountered a Windows/Docker PostgreSQL SSL-negotiation reset.
  The disposable database fixture now explicitly disables TLS for that local test container;
  all cases passed on rerun. Production connection security settings were not changed.

# Hold funds on acceptance (#70)

## Branch and integration scope

This implements hold persistence, the RequestAccepted consumer, background authorization,
outcome events and explicit capture on the #67 story branch. It does not merge #151 or
add its customer/card tables or endpoints.

SavedCardLookup remains an application interface. ConfiguredSavedCardLookup is a real,
per-rider sandbox adapter populated from operator-supplied Stripe references. An unmapped
rider raises a configuration error; it is not reported as no_card. Stripe verifies that
the supplied payment method belongs to the supplied customer when authorizing.

Automatic processing is disabled by default. To enable it locally, configure these values
in the root, gitignored .env (replace every example ID with a real reference):

```dotenv
PAYMENTS_STRIPE_SECRET_KEY=sk_test_replace_me
PAYMENTS_HOLD_PROCESSING_ENABLED=true
PAYMENTS_SAVED_CARD_REFERENCES='{"00000000-0000-0000-0000-000000000001":{"customer_id":"cus_example","payment_method_id":"pm_example"}}'
```

The UUID must be the riderId in RequestAccepted, and both Stripe IDs must belong to the
same sandbox as the secret key. No card number, CVC or client secret belongs in this map.
The app uses this lookup automatically; an explicitly injected lookup still takes priority.
Local Compose forwards these settings to Payments. Its default remains disabled.
Do not enable a shared server without configuring every participating rider.

This is operator-configured test-mode integration, not automatic onboarding: adding or
changing a card through the UI remains #151. That later integration can replace this
adapter without changing hold logic or merging #151 into this task.

## Flow

1. RequestAccepted is consumed from events.trips by the payments consumer group. Its saved
   amount, currency and identities are inserted into payments.payment_holds. There is no
   call to pricing and no second distance calculation.
2. The request ID is unique in the database. Identical duplicates do nothing; a conflicting
   duplicate cannot overwrite the saved quote. processed_events additionally deduplicates
   re-delivery of the same event envelope.
3. A worker locks the hold, obtains SavedPaymentCard(customer_id, payment_method_id) from
   the lookup and commits those references before calling Stripe. The snapshot survives
   worker crashes and retries even if the rider later changes their default card.
4. Authorization is off-session, manual capture, with key hold:<request-id>. Only a returned
   requires_capture status produces AUTHORIZED and PaymentHeld. The hold and its outbox
   event commit together; the relay publishes to events.payments.
5. A missing card, decline or authentication requirement produces FAILED and PaymentFailed
   with the existing contract reason. A lookup/configuration outage is not a missing card.
6. Transient gateway failures retry with exactly the saved parameters and key after 30s.
   Row locks serialize workers. A retry after provider success and a database rollback
   reuses Stripe's idempotent response instead of creating a second hold.
7. HoldWorker.capture(request_id) captures the same authorized PaymentIntent using
   capture:<request-id>. It persists CAPTURED only after succeeded. Repeating a completed
   capture does nothing. It is not wired to trip completion until #71 and has no public API.

Existing events and OpenAPI shapes are unchanged. No card numbers, client secrets or
payment-method references are added to event payloads.

## Safety boundaries and follow-up tasks

- Holds expose SCHEDULED, AUTHORIZED, CAPTURED, RELEASED and FAILED. RELEASED behaviour is #72.
- The consumer acknowledges expired acceptances and zero-cent shares without creating
  holds or publishing PaymentFailed. New groups can replay history without notifying old riders.
- An unattempted queued hold that expires is marked FAILED silently. A prepared/uncertain
  attempt is paused for reconciliation, without publishing a misleading payment failure.
- Stripe idempotency keys can expire after 24 hours. Automatic retries stop conservatively
  at 23 hours from the persisted first attempt. SCHEDULED with retry_at=NULL means manual
  provider reconciliation is required; it is not a successful hold or a card decline.
- Unexpected provider states (including processing or an unexpected succeeded result)
  preserve the Stripe ID and pause for reconciliation. They never publish PaymentHeld.
- #153 extends failure handling, including operational visibility and recovery for
  SCHEDULED rows with retry_at=NULL (stuck reconciliation). #154 schedules far-ahead bookings around authorization
  windows; the immediate worker here is not that scheduler.
- When #151 is replayed on the integrated payment foundation, its customers migration must
  descend from a70000000001 rather than remain a second root. No #151 migration is copied
  into this task.

## Test

Start Docker Desktop's Linux engine, then from the repository root:

```powershell
uv sync --locked
uv run pytest services/payments -rs
uv run ruff format --check services/payments
uv run ruff check services/payments
uv run mypy services/payments/src
Push-Location services/payments
uv run lint-imports
Pop-Location
```

The integration fixtures migrate a fresh throwaway PostgreSQL database, not the local
payments database. Redis tests publish duplicate RequestAccepted envelopes. Concurrent
workers must create one provider intent and one PaymentHeld outbox entry for exactly the
saved amount. A crash after provider success tests recovery with unchanged credentials
and key. Capture tests verify one call for the same Stripe intent. Unit tests cover failure
reasons, uncertain statuses and retry cutoffs. #68's SDK tests check manual capture and
off-session request serialization; stripe-mock checks SDK schema compatibility.

For local migration after integration, first ensure the current database's Alembic revision
belongs to this branch. A database already migrated on the separate #151 branch is not a
clean #70 database; do not delete its migration stamp or reset its tables to make it fit.
Docker applies the migration through the existing service entrypoint on a compatible base.

## Verification recorded on 2026-11-15

- Normal Payments suite: 91 passed; only the opt-in sandbox test skipped.
- Opt-in real Stripe test: 1 passed. Verified PaymentIntent
  `pi_3UcDYmIQXqskkTT20cMVJOyk` for 625 CAD cents, manual capture,
  `requires_capture`, zero received, and exactly one intent after duplicate acceptance.
- The test cancelled that authorization in cleanup; it did not capture a payment.
- Formatting, lint, strict types, architecture checks and local Compose validation passed.
- No #151 commits, customer tables or card-setup endpoints were merged into this branch.

## Real Stripe sandbox verification (opt-in)

The following test creates a dedicated sandbox customer and attaches Stripe's standard
pm_card_visa test payment method. It runs the normal configured app, Redis consumer and
worker with a fresh PostgreSQL database. It checks requires_capture, manual capture,
625 CAD cents and zero amount received, then replays acceptance and checks one intent and
one PaymentHeld. It finally cancels the uncaptured test authorization. No capture is made.
It never migrates or resets a developer database, and it does not need #151's code.

Run from the repository root with Docker running and a real test secret key in .env.
Remove PAYMENTS_STRIPE_API_BASE overrides so the test uses https://api.stripe.com.

```powershell
$env:RUN_STRIPE_SANDBOX_HOLD="1"
uv run pytest services/payments/tests/test_stripe_sandbox_hold.py -q -s
Remove-Item Env:RUN_STRIPE_SANDBOX_HOLD
```

It prints only the verified PaymentIntent ID and status, never keys or client secrets.
In the same Stripe sandbox's Dashboard, look up that ID. The test verifies its uncaptured
state before cleanup; after cleanup it appears cancelled, with no captured payment.
The regular suite skips this test unless RUN_STRIPE_SANDBOX_HOLD=1 is explicitly supplied.
A pass verifies the event-to-provider component; real UI onboarding and trip-completion
integration remain the responsibilities of #151 and #71.

References: [manual capture](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method),
[idempotency](https://docs.stripe.com/api/idempotent_requests).

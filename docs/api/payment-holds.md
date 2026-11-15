# Hold funds on acceptance (#70)

## Branch and integration scope

This implements the hold domain, persistence, RequestAccepted consumer, background worker,
outcome events and explicit capture use case on the #67 story branch. It does not merge
#151 or add customer/card storage. SavedCardLookup is an injected application interface;
tests provide fake Stripe references. The live adapter for that interface will be connected
when #151 is integrated through develop.

Automatic processing is disabled by default. PAYMENTS_HOLD_PROCESSING_ENABLED=true requires
both a Stripe test secret key and an implementation supplied to create_app(saved_cards=...).
Startup fails if either is missing. Do not enable it with a fake lookup on a shared server.
This branch alone does not prove a real rider's acceptance creates a dashboard-visible hold;
that end-to-end check remains pending the saved-card integration. Do not close #70 on the
basis of fake-gateway tests alone.

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
- No new authorization is started from an old accepted event after departure. An uncertain
  existing attempt at that point is paused for reconciliation rather than charged blindly.
- Stripe idempotency keys can expire after 24 hours. Automatic retries stop conservatively
  at 23 hours from the persisted first attempt. SCHEDULED with retry_at=NULL means manual
  provider reconciliation is required; it is not a successful hold or a card decline.
- Unexpected provider states (including processing or an unexpected succeeded result)
  preserve the Stripe ID and pause for reconciliation. They never publish PaymentHeld.
- #153 extends failure handling. #154 schedules far-ahead bookings around authorization
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

## Remaining manual verification

After the real saved-card lookup is connected, use a rider with a Stripe sandbox card,
request and accept a trip, and verify one uncaptured PaymentIntent for the saved quote.
Replay the acceptance event and verify there is still only one hold. Do not manually
capture it as part of the normal acceptance flow. Capture-on-completion belongs to #71.

References: [manual capture](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method),
[idempotency](https://docs.stripe.com/api/idempotent_requests).

# Payment failure handling (#153)

## Behaviour

Payments already maps definitive no-card, decline and authentication-required outcomes to
PaymentFailed and commits that event with the FAILED hold through its outbox. It does not
recalculate the saved quote. Transient outages and uncertain provider outcomes are not
reported as definitive card failures.

Trips now consumes events.payments as the trips consumer group. For PaymentFailed:

1. Validate that requestId, tripId and riderId match the saved request.
2. Lock the trip using the same lock order as accept/decline/cancel, then reload the request.
3. Transition an accepted request to payment_failed using a conditional status update.
4. Return its seat and renumber the remaining accepted pickups in the same transaction.
5. Commit that change with the shared consumer's processed_events record.

A repeated event, an already-failed request, or a request already cancelled/declined does
not return another seat. The saved distance and quote are unchanged. Unknown or mismatched
identities cause retry/parking rather than returning a seat belonging to somebody else.
No extra RequestCancelled or PaymentFailed event is published by Trips.

Notifications' existing PaymentFailed handler removes the rider from active trip membership
and creates a plain-language in-app notification and email. Its reminder handler also
cancels the failed request's departure reminder by requestId, leaving other riders'
reminders unchanged. It distinguishes a declined
card, a bank authentication requirement and no saved card, and tells the rider to check
their card and request a seat again. Outbox redelivery keeps the same event ID; each service
records it independently and does not repeat its successful effect.

No new API or event fields are introduced. The payment_failed request status and
PaymentFailed reason codes were already in the published contracts.

## Migration and runtime

Trips migration a15300000001 follows a31000000001 and adds processed_events and failed_events
in the trips schema. The payment failure consumer starts with the Trips service alongside
its existing outbox relay. It subscribes only to events.payments and uses its own group,
so it does not take events away from Notifications.

From the repository root, on the compatible #67 database chain:

```powershell
uv run --package trips alembic -c services/trips/alembic.ini upgrade head
```

Docker applies the migration through the shared entrypoint. Tests always migrate disposable
containers, not the developer database.

## Tests

```powershell
uv run pytest services/trips/tests/test_payment_failed.py -q
uv run pytest tests/integration/test_payment_failure_flow.py -rs
uv run pytest services/payments services/trips services/notifications tests/integration -rs
uv run ruff check services/trips tests/integration
uv run mypy services/trips/src
```

The multi-service test is at workspace level because service unit tests must not import
another service's implementation. It migrates isolated Payments, Trips and Notifications
schemas and uses real Redis consumers and the Payments outbox relay. Fake gateway cases
cover card_declined and authentication_required. It checks that a failed accepted rider's
seat is returned once, the other rider moves from pickup order 2 to 1, the quote stays
unchanged, the failed rider's reminder is cancelled while the other rider's stays pending,
and one clear in-app notification and prepared email are produced.

Contact lookup and email sending are fakes: the tests do not contact Accounts or send real
email. Notifications already has its own SMTP tests. The integration path is included in
the root pytest testpaths and therefore runs in normal workspace CI.

### Real declined-card sandbox check (opt-in)

With Docker running, a real PAYMENTS_STRIPE_SECRET_KEY in the root .env and no mock API base:

```powershell
$env:RUN_STRIPE_SANDBOX_FAILURE="1"
uv run pytest tests/integration/test_payment_failure_flow.py -q -s
Remove-Item Env:RUN_STRIPE_SANDBOX_FAILURE
```

The opt-in case creates a dedicated sandbox customer and Stripe's pm_card_chargeCustomerFail
test method. The actual Stripe adapter produces the failure and the three-service flow
must mark the request failed, return the seat and notify the fake test rider. It verifies
that the failed PaymentIntent received zero funds. Test notifications and database records
are disposable; no real email is sent. Any unexpected uncaptured authorization is cancelled
in cleanup. The normal suite skips this API-writing case unless explicitly enabled.

## Uncertain payments and reconciliation

A stuck SCHEDULED hold with retry_at=NULL is not a card decline. Likewise, a pending release
with an uncertain or captured provider outcome must not produce a false PaymentReleased.
The existing hold worker logs that provider reconciliation is required, with the seat
request ID, without logging card details.

Operators can inspect candidates with this read-only query in the Payments database:

```sql
SELECT request_id, trip_id, status, stripe_id, release_requested, first_attempt_at
FROM payments.payment_holds
WHERE retry_at IS NULL
  AND (status = 'SCHEDULED'
       OR (release_requested AND status NOT IN ('FAILED', 'RELEASED')));
```

Compare the recorded Stripe intent and original operation with the sandbox Dashboard before
resuming anything. Do not reset an expired authorization idempotency key or publish a fake
PaymentFailed to free the seat: the provider may already hold funds. Automated resolution of
ambiguous outcomes is not part of the definitive-failure transition implemented here.

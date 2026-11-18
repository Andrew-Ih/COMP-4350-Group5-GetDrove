# ADR 0025: Holds are placed on a saved card by a background worker, from Trips' events

- **Status:** Proposed
- **Date:** 2026-11-18

## Context

Riders are charged only after the trip happens, but the money must be secured when they're accepted ([#67](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/67)): a hold (a Stripe PaymentIntent with manual capture) when the driver accepts, released if the ride is cancelled or declined, captured after the trip (Sprint 3). Three things shaped how:

1. **The rider isn't there when the hold is placed.** The driver accepts, often hours later. So the card must already be saved, and the hold placed without the rider (off-session).
2. **Stripe holds expire.** An uncaptured card authorization lasts about 7 days, but riders can book a recurring trip weeks ahead.
3. **Accepting mustn't depend on Stripe.** The driver's accept, the seat count and the event are one transaction in Trips ([ADR 0024](0024-seat-counting.md)); calling Stripe inside it would make accepting slow, and fail whenever Stripe does.

## Options considered

- **Trips calls Payments synchronously on accept:** simple, but accepting then fails when Payments or Stripe is down, and a timeout leaves it unclear whether money was held.
- **Hold at request time, before the driver decides:** riders would have money held for requests that are never accepted.
- **Payments consumes `RequestAccepted` and calls Stripe inside the event handler:** decoupled, but a Stripe call inside the event's database transaction holds the transaction open, and a crash between Stripe's answer and the commit loses what happened.

## Decision

- **A saved card is required to request a seat.** Riders save a card once with a Stripe SetupIntent (usage `off_session`) in the web app; card details go straight from the browser to Stripe. Payments keeps only Stripe's customer and payment method IDs. Trips checks `GET /internal/customers/{id}/card` before creating a request (`409 card_required`).
- **Payments consumes `RequestAccepted` and saves a scheduled hold**, with the amount the rider was quoted. It's due straight away, or **24 hours before departure** when the trip is more than 6 days away, so the authorization never expires before the ride.
- **A background hold worker** in Payments places due holds in two steps: it snapshots the card and records the attempt, commits, then calls Stripe with the idempotency key `hold:<request-id>`, and records the result. A retry after a crash makes the same call with the same key, so Stripe never holds twice. Attempts stop after 23 hours, inside Stripe's idempotency window, and are left for an operator rather than risk a second hold.
- **Outcomes are events through the outbox:** `PaymentHeld`; or `PaymentFailed` (declined, needs authentication, no card), which makes Trips mark the request `payment_failed` and give the seat back, and Notifications tell the rider. `RequestDeclined`, `RequestCancelled` and `TripCancelled` mark the hold for release; the worker cancels the PaymentIntent and publishes `PaymentReleased`.
- Hold processing has a switch (`PAYMENTS_HOLD_PROCESSING_ENABLED`), on in production and off by default locally, so developers without a Stripe key aren't affected.

## Consequences

**Positive**

- Accepting is as fast and reliable as before; Stripe being down only delays the hold.
- No double holds and no lost outcomes across crashes and repeated events.
- Holds never expire before a far-ahead ride, and a rider whose card fails loses the seat cleanly instead of riding unpaid.

**Negative / trade-offs**

- A rider is "accepted" for a moment before their card is held. If the hold then fails, they lose the seat after being told they're in; Notifications explains why. Requiring a saved card first makes this rare.
- More moving parts in Payments: a worker loop, scheduled holds and a state machine (scheduled, authorized, captured, released, failed). Each transition has tests; the real-Stripe tests are opt-in (see the [testing strategy](../../testing/testing-strategy.md#gaps)).
- The first production start replays Trips' event history, so accepted seats on upcoming trips get holds scheduled, and riders without a saved card lose those seats (checked before the v0.2.0 release; see [deployment](../../deployment/deployment.md#saved-card-payment-holds-428)).

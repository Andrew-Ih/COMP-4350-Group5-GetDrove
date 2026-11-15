"""Authorize the saved quote; no pricing service or distance calculation is used here."""

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID

from payments.application.ports import (
    AuthenticationRequiredError,
    GatewayUnavailableError,
    HoldEvents,
    HoldRepository,
    PaymentDeclinedError,
    PaymentGatewayError,
    PaymentGatewayPort,
    PaymentIntentStatus,
    SavedCardLookup,
)
from payments.domain.holds import FailureReason, HoldStatus, PaymentHold


class HoldConflictError(Exception):
    """A request ID was reused with a different saved quote or identity."""


class HoldNeedsReconciliationError(Exception):
    """Provider state is uncertain; do not retry authorization with a fresh key."""


class HoldPayments:
    def __init__(
        self,
        holds: HoldRepository,
        cards: SavedCardLookup,
        gateway: PaymentGatewayPort,
        events: HoldEvents,
    ) -> None:
        self.holds = holds
        self.cards = cards
        self.gateway = gateway
        self.events = events

    async def prepare(self, request_id: UUID, now: datetime) -> None:
        """Commit this phase before authorize: provider parameters survive crashes/retries."""
        hold = await self.holds.lock(request_id)
        if hold is None or hold.status is not HoldStatus.SCHEDULED:
            return
        if hold.card is not None:
            return
        if now >= hold.departure_at:
            await self._fail(hold, "other")
            return
        card = await self.cards.for_rider(hold.rider_id)
        if card is None:
            await self._fail(hold, "no_card")
        else:
            await self.holds.save(replace(hold, card=card, first_attempt_at=now))

    async def authorize(self, request_id: UUID, now: datetime) -> None:
        hold = await self.holds.lock(request_id)
        if hold is None or hold.status is not HoldStatus.SCHEDULED or hold.retry_at is None:
            return
        if hold.card is None or hold.first_attempt_at is None:
            return
        if now < hold.retry_at:
            return
        # Stripe may prune idempotency keys after 24h. Never blindly retry beyond that window.
        if now >= hold.departure_at or now - hold.first_attempt_at >= timedelta(hours=23):
            await self.holds.save(replace(hold, retry_at=None))
            return
        try:
            result = await self.gateway.authorize(
                customer_id=hold.card.customer_id,
                payment_method_id=hold.card.payment_method_id,
                amount_cents=hold.amount_cents,
                currency=hold.currency,
                idempotency_key=f"hold:{hold.request_id}",
            )
        except GatewayUnavailableError:
            await self.holds.save(replace(hold, retry_at=now + timedelta(seconds=30)))
            return
        except AuthenticationRequiredError:
            await self._fail(hold, "authentication_required")
            return
        except PaymentDeclinedError:
            await self._fail(hold, "card_declined")
            return
        except PaymentGatewayError:
            # Parameter/configuration errors may require operator intervention.
            await self.holds.save(replace(hold, retry_at=None))
            return
        hold = replace(hold, stripe_id=result.id)
        if result.status is PaymentIntentStatus.REQUIRES_CAPTURE:
            hold = replace(hold, status=HoldStatus.AUTHORIZED, retry_at=None)
            await self.holds.save(hold)
            await self.events.held(hold)
        elif result.status is PaymentIntentStatus.REQUIRES_ACTION:
            await self._fail(hold, "authentication_required")
        elif result.status in (
            PaymentIntentStatus.REQUIRES_PAYMENT_METHOD,
            PaymentIntentStatus.CANCELED,
        ):
            await self._fail(hold, "card_declined")
        else:
            # Processing/unexpected success isn't evidence of an uncaptured hold.
            await self.holds.save(replace(hold, retry_at=None))

    async def _fail(self, hold: PaymentHold, reason: FailureReason) -> None:
        failed = replace(hold, status=HoldStatus.FAILED, retry_at=None)
        await self.holds.save(failed)
        await self.events.failed(failed, reason)

    async def capture(self, request_id: UUID) -> PaymentHold:
        """Built for #70, deliberately not connected to trip completion until #71."""
        hold = await self.holds.lock(request_id)
        if hold is None:
            raise ValueError("Unknown payment hold")
        if hold.status is HoldStatus.CAPTURED:
            return hold
        if hold.status is not HoldStatus.AUTHORIZED or hold.stripe_id is None:
            raise ValueError("Only an authorized hold can be captured")
        result = await self.gateway.capture(
            payment_intent_id=hold.stripe_id, idempotency_key=f"capture:{hold.request_id}"
        )
        if result.id != hold.stripe_id or result.status is not PaymentIntentStatus.SUCCEEDED:
            raise HoldNeedsReconciliationError("Capture did not report success")
        captured = replace(hold, status=HoldStatus.CAPTURED)
        await self.holds.save(captured)
        return captured

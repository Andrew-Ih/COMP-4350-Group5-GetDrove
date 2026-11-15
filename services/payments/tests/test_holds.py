"""#70 uses the saved #69 amount and fake card references, without importing #151."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from payments.application.holds import HoldNeedsReconciliationError, HoldPayments
from payments.application.ports import (
    AuthenticationRequiredError,
    GatewayUnavailableError,
    PaymentDeclinedError,
    PaymentGatewayError,
    PaymentGatewayPort,
    PaymentIntentResult,
    PaymentIntentStatus,
)
from payments.domain.holds import HoldStatus, PaymentHold, SavedPaymentCard

NOW = datetime(2030, 1, 1, tzinfo=UTC)
CARD = SavedPaymentCard("cus_test", "pm_card_visa")


def saved_hold() -> PaymentHold:
    return PaymentHold(
        request_id=uuid4(),
        trip_id=uuid4(),
        rider_id=uuid4(),
        driver_id=uuid4(),
        amount_cents=625,
        currency="CAD",
        departure_at=NOW + timedelta(hours=12),
        retry_at=NOW,
    )


class MemoryHolds:
    def __init__(self, hold: PaymentHold) -> None:
        self.items = {hold.request_id: hold}

    async def lock(self, request_id: UUID) -> PaymentHold | None:
        return self.items.get(request_id)

    async def save(self, hold: PaymentHold) -> None:
        self.items[hold.request_id] = hold


class Setup:
    def __init__(self) -> None:
        self.hold = saved_hold()
        self.holds = MemoryHolds(self.hold)
        self.cards = AsyncMock()
        self.cards.for_rider.return_value = CARD
        self.gateway = AsyncMock()
        self.gateway.authorize.return_value = PaymentIntentResult(
            "pi_test", PaymentIntentStatus.REQUIRES_CAPTURE
        )
        self.gateway.capture.return_value = PaymentIntentResult(
            "pi_test", PaymentIntentStatus.SUCCEEDED
        )
        self.events = AsyncMock()
        self.use_case = HoldPayments(
            self.holds, self.cards, cast(PaymentGatewayPort, self.gateway), self.events
        )

    @property
    def stored(self) -> PaymentHold:
        return self.holds.items[self.hold.request_id]

    async def authorize(self) -> None:
        await self.use_case.prepare(self.hold.request_id, NOW)
        await self.use_case.authorize(self.hold.request_id, NOW)


async def test_authorization_uses_saved_amount_and_is_not_a_charge() -> None:
    s = Setup()
    await s.authorize()
    s.gateway.authorize.assert_awaited_once_with(
        customer_id=CARD.customer_id,
        payment_method_id=CARD.payment_method_id,
        amount_cents=625,
        currency="CAD",
        idempotency_key=f"hold:{s.hold.request_id}",
    )
    assert s.stored.status is HoldStatus.AUTHORIZED
    assert s.stored.stripe_id == "pi_test"
    s.gateway.capture.assert_not_awaited()
    s.events.held.assert_awaited_once_with(s.stored)


async def test_duplicate_processing_creates_no_second_hold_or_event() -> None:
    s = Setup()
    await s.authorize()
    await s.authorize()
    s.gateway.authorize.assert_awaited_once()
    s.events.held.assert_awaited_once()


async def test_transient_failure_reuses_snapshot_key_and_saved_amount() -> None:
    s = Setup()
    s.gateway.authorize.side_effect = [
        GatewayUnavailableError(),
        PaymentIntentResult("pi_test", PaymentIntentStatus.REQUIRES_CAPTURE),
    ]
    await s.authorize()
    assert s.stored.status is HoldStatus.SCHEDULED
    s.events.failed.assert_not_awaited()
    s.cards.for_rider.return_value = SavedPaymentCard("cus_changed", "pm_changed")
    await s.use_case.prepare(s.hold.request_id, NOW + timedelta(seconds=31))
    await s.use_case.authorize(s.hold.request_id, NOW + timedelta(seconds=31))
    calls = s.gateway.authorize.await_args_list
    assert calls[0] == calls[1]
    assert s.stored.status is HoldStatus.AUTHORIZED
    s.cards.for_rider.assert_awaited_once()


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (PaymentDeclinedError(), "card_declined"),
        (AuthenticationRequiredError(), "authentication_required"),
    ],
)
async def test_decline_and_authentication_publish_failure(failure, reason) -> None:
    s = Setup()
    s.gateway.authorize.side_effect = failure
    await s.authorize()
    assert s.stored.status is HoldStatus.FAILED
    s.events.failed.assert_awaited_once_with(s.stored, reason)
    s.events.held.assert_not_awaited()


async def test_no_card_fails_but_lookup_outage_does_not_mean_no_card() -> None:
    s = Setup()
    s.cards.for_rider.return_value = None
    await s.authorize()
    s.gateway.authorize.assert_not_awaited()
    s.events.failed.assert_awaited_once_with(s.stored, "no_card")
    s = Setup()
    s.cards.for_rider.side_effect = RuntimeError("Lookup not configured")
    with pytest.raises(RuntimeError):
        await s.use_case.prepare(s.hold.request_id, NOW)
    assert s.stored.status is HoldStatus.SCHEDULED
    s.events.failed.assert_not_awaited()


@pytest.mark.parametrize(
    "status",
    [
        PaymentIntentStatus.PROCESSING,
        PaymentIntentStatus.SUCCEEDED,
        PaymentIntentStatus.REQUIRES_CONFIRMATION,
    ],
)
async def test_non_authorized_status_never_publishes_held(status) -> None:
    s = Setup()
    s.gateway.authorize.return_value = PaymentIntentResult("pi_test", status)
    await s.authorize()
    assert s.stored.status is HoldStatus.SCHEDULED
    assert s.stored.retry_at is None
    assert s.stored.stripe_id == "pi_test"
    s.events.held.assert_not_awaited()


async def test_expired_idempotency_window_and_configuration_errors_stop_automatic_retries() -> None:
    s = Setup()
    s.holds.items[s.hold.request_id] = replace(s.hold, departure_at=NOW + timedelta(days=3))
    await s.use_case.prepare(s.hold.request_id, NOW)
    await s.use_case.authorize(s.hold.request_id, NOW + timedelta(hours=24))
    assert s.stored.retry_at is None
    s.gateway.authorize.assert_not_awaited()
    s = Setup()
    s.gateway.authorize.side_effect = PaymentGatewayError()
    await s.authorize()
    assert s.stored.retry_at is None
    s.events.held.assert_not_awaited()
    s.events.failed.assert_not_awaited()


async def test_capture_is_explicit_and_idempotent_on_the_same_payment_intent() -> None:
    s = Setup()
    await s.authorize()
    await s.use_case.capture(s.hold.request_id)
    result = await s.use_case.capture(s.hold.request_id)
    assert result.status is HoldStatus.CAPTURED
    assert result.amount_cents == 625
    s.gateway.capture.assert_awaited_once_with(
        payment_intent_id="pi_test", idempotency_key=f"capture:{s.hold.request_id}"
    )


async def test_capture_rejects_wrong_state_or_uncertain_provider_response() -> None:
    s = Setup()
    with pytest.raises(ValueError):
        await s.use_case.capture(s.hold.request_id)
    s.gateway.capture.assert_not_awaited()
    await s.authorize()
    s.gateway.capture.return_value = PaymentIntentResult("pi_other", PaymentIntentStatus.SUCCEEDED)
    with pytest.raises(HoldNeedsReconciliationError):
        await s.use_case.capture(s.hold.request_id)
    assert s.stored.status is HoldStatus.AUTHORIZED


async def test_old_accepted_event_does_not_authorize_after_departure() -> None:
    s = Setup()
    await s.use_case.prepare(s.hold.request_id, NOW + timedelta(days=1))
    assert s.stored.status is HoldStatus.FAILED
    s.gateway.authorize.assert_not_awaited()
    s.events.failed.assert_awaited_once_with(s.stored, "other")


async def test_enabled_runtime_requires_explicit_saved_card_integration(monkeypatch) -> None:
    import payments.infrastructure.main as main
    from payments.infrastructure.settings import Settings

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, hold_processing_enabled=True, stripe_secret_key=None),
    )
    app = main.create_app()
    with pytest.raises(RuntimeError, match="saved-card lookup"):
        async with app.router.lifespan_context(app):
            pass

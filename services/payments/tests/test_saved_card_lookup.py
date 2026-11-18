"""Saved cards drive holds without transactions or locks during Stripe discovery."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from payments.adapters.persistence.customers import SQLAlchemyCustomers
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.adapters.persistence.tables import customers, outbox, payment_holds
from payments.adapters.saved_cards import CustomerSavedCardLookup
from payments.application.ports import (
    GatewayUnavailableError,
    PaymentGatewayPort,
    PaymentIntentResult,
    PaymentIntentStatus,
)
from payments.domain.cards import SavedCard
from payments.domain.holds import HoldStatus, PaymentHold, SavedPaymentCard
from payments.infrastructure.hold_worker import HoldWorker


@pytest.fixture
async def scenario(payments_database):
    engine = create_async_engine(payments_database, hide_parameters=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    hold = PaymentHold(
        request_id=uuid4(),
        trip_id=uuid4(),
        rider_id=uuid4(),
        driver_id=uuid4(),
        amount_cents=625,
        currency="CAD",
        departure_at=now + timedelta(hours=12),
        authorize_at=now,
        retry_at=now,
    )
    customer_id = f"cus_{hold.rider_id.hex}"
    gateway = AsyncMock()
    gateway.list_cards.return_value = [SavedCard("pm_old", "visa", "4242", 12, 2030, 1)]
    gateway.authorize.return_value = PaymentIntentResult(
        "pi_saved", PaymentIntentStatus.REQUIRES_CAPTURE
    )
    lookup = CustomerSavedCardLookup(sessions, cast(PaymentGatewayPort, gateway))
    clock = [now]
    worker = HoldWorker(sessions, lookup, cast(PaymentGatewayPort, gateway), clock=lambda: clock[0])
    async with sessions() as session, session.begin():
        # run_once scans all holds; other scenarios' queued work must not enter this one.
        await session.execute(delete(payment_holds))
        await session.execute(
            insert(customers).values(
                user_id=hold.rider_id,
                stripe_customer_id=customer_id,
            )
        )
        await SQLAlchemyHolds(session).schedule(hold)
    try:
        yield engine, sessions, gateway, lookup, worker, hold, customer_id, clock
    finally:
        await engine.dispose()


async def stored(sessions, request_id):
    async with sessions() as session:
        return await SQLAlchemyHolds(session).get(request_id)


async def outcomes(sessions, request_id):
    async with sessions() as session:
        return list(
            (
                await session.execute(
                    select(outbox.c.type).where(
                        outbox.c.envelope["payload"]["requestId"].astext == str(request_id)
                    )
                )
            ).scalars()
        )


async def test_lookup_is_per_user_and_unknown_user_creates_no_mapping(scenario):
    _, sessions, gateway, lookup, _, hold, customer_id, _ = scenario
    unknown = uuid4()
    assert await lookup.for_rider(unknown) is None
    gateway.list_cards.assert_not_awaited()
    async with sessions() as session:
        assert await SQLAlchemyCustomers(session).get(unknown) is None
    gateway.list_cards.return_value = [
        SavedCard("pm_old", "visa", "4242", 12, 2030, 1),
        SavedCard("pm_new", "visa", "4242", 12, 2030, 2),
    ]
    assert await lookup.for_rider(hold.rider_id) == SavedPaymentCard(customer_id, "pm_new")
    gateway.list_cards.assert_awaited_once_with(customer_id=customer_id)
    async with sessions() as session:
        assert (
            await SQLAlchemyCustomers(session).get(hold.rider_id)
        ).default_payment_method_id == "pm_new"


async def test_empty_stripe_list_fails_hold_with_no_card(scenario):
    _, sessions, gateway, _, worker, hold, _, _ = scenario
    gateway.list_cards.return_value = []
    assert await worker.run_once() == 1
    failed = await stored(sessions, hold.request_id)
    assert failed.status is HoldStatus.FAILED
    gateway.authorize.assert_not_awaited()
    async with sessions() as session:
        reason = (
            await session.execute(
                select(outbox.c.envelope).where(
                    outbox.c.envelope["payload"]["requestId"].astext == str(hold.request_id)
                )
            )
        ).scalar_one()["payload"]["reason"]
        assert reason == "no_card"


@pytest.mark.parametrize("failure", ["provider", "database"])
async def test_lookup_outage_retries_without_false_payment_failure(scenario, monkeypatch, failure):
    _, sessions, gateway, _, worker, hold, _, clock = scenario
    original = SQLAlchemyCustomers.get
    if failure == "provider":
        gateway.list_cards.side_effect = GatewayUnavailableError()
    else:

        async def unavailable(*args):
            raise RuntimeError("Database unavailable")

        monkeypatch.setattr(SQLAlchemyCustomers, "get", unavailable)
    assert await worker.run_once() == 1
    pending = await stored(sessions, hold.request_id)
    assert pending.status is HoldStatus.SCHEDULED
    assert pending.first_attempt_at is None
    assert pending.retry_at == clock[0] + timedelta(seconds=30)
    assert await outcomes(sessions, hold.request_id) == []
    gateway.authorize.assert_not_awaited()
    gateway.list_cards.side_effect = None
    monkeypatch.setattr(SQLAlchemyCustomers, "get", original)
    clock[0] += timedelta(seconds=30)
    assert await worker.run_once() == 1
    assert (await stored(sessions, hold.request_id)).status is HoldStatus.AUTHORIZED


async def test_far_ahead_authorization_uses_latest_card_only_when_due(scenario):
    _, sessions, gateway, _, worker, hold, customer_id, clock = scenario
    due = clock[0] + timedelta(days=13)
    async with sessions() as session, session.begin():
        # Replace this unattempted scenario with the actual far-ahead schedule.
        await session.execute(delete(payment_holds))
        await SQLAlchemyHolds(session).schedule(
            replace(
                hold,
                departure_at=due + timedelta(days=1),
                authorize_at=due,
                retry_at=due,
            )
        )
    assert await worker.run_once() == 0
    await worker.process(hold.request_id)
    gateway.list_cards.assert_not_awaited()
    gateway.list_cards.return_value = [SavedCard("pm_at_departure", "visa", "4242", 12, 2030, 4)]
    clock[0] = due
    assert await worker.run_once() == 1
    gateway.authorize.assert_awaited_once_with(
        customer_id=customer_id,
        payment_method_id="pm_at_departure",
        amount_cents=625,
        currency="CAD",
        idempotency_key=f"hold:{hold.request_id}",
    )
    assert (await stored(sessions, hold.request_id)).first_attempt_at == due


async def test_retry_preserves_committed_card_and_key_without_another_lookup(scenario):
    _, sessions, gateway, _, worker, hold, customer_id, clock = scenario
    gateway.authorize.side_effect = [
        GatewayUnavailableError(),
        PaymentIntentResult("pi_recovered", PaymentIntentStatus.REQUIRES_CAPTURE),
    ]
    await worker.process(hold.request_id)
    gateway.list_cards.return_value = [SavedCard("pm_changed", "visa", "4242", 12, 2030, 3)]
    clock[0] += timedelta(seconds=31)
    await worker.process(hold.request_id)
    assert gateway.authorize.await_args_list[0] == gateway.authorize.await_args_list[1]
    assert gateway.authorize.await_args.kwargs["payment_method_id"] == "pm_old"
    gateway.list_cards.assert_awaited_once_with(customer_id=customer_id)
    assert await outcomes(sessions, hold.request_id) == ["PaymentHeld"]


async def test_cancellation_during_card_discovery_holds_no_locks_and_wins(scenario):
    engine, sessions, gateway, _, worker, hold, _, clock = scenario

    async def cancel_while_stripe_pages(*, customer_id):
        assert engine.pool.checkedout() == 0
        async with asyncio.timeout(5):
            async with sessions() as session, session.begin():
                await SQLAlchemyHolds(session).request_release(
                    hold.request_id, hold.trip_id, hold.rider_id, hold.driver_id, None, clock[0]
                )
        return [SavedCard("pm_late", "visa", "4242", 12, 2030, 2)]

    gateway.list_cards.side_effect = cancel_while_stripe_pages
    await worker.process(hold.request_id)
    assert (await stored(sessions, hold.request_id)).status is HoldStatus.RELEASED
    gateway.authorize.assert_not_awaited()
    assert await outcomes(sessions, hold.request_id) == ["PaymentReleased"]

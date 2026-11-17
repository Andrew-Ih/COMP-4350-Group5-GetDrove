"""Real consumer/database/outbox tests with an injected, idempotent fake provider."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from events import EventEnvelope, stream_name
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from payments.adapters.hold_events import (
    register_hold_handlers,
    release_request,
    release_trip,
    schedule_accepted,
)
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.adapters.persistence.tables import consumer as tables
from payments.adapters.persistence.tables import outbox, payment_holds
from payments.application.ports import (
    PaymentDeclinedError,
    PaymentGatewayPort,
    PaymentIntentResult,
    PaymentIntentStatus,
)
from payments.domain.holds import HoldStatus, SavedPaymentCard
from payments.infrastructure.hold_worker import HoldWorker

NOW = datetime.now(UTC)


def accepted() -> EventEnvelope:
    return EventEnvelope.wrap(
        RequestAccepted(
            request_id=uuid4(),
            trip_id=uuid4(),
            rider_id=uuid4(),
            driver_id=uuid4(),
            departure_at=NOW + timedelta(hours=12),
            pickup_label="Test pickup",
            direction="to_campus",
            amount_cents=625,
            currency="CAD",
            auto_accepted=False,
        ),
        producer="trips",
        correlation_id=str(uuid4()),
    )


class Provider:
    def __init__(self) -> None:
        self.intents: dict[str, PaymentIntentResult] = {}
        self.gateway = AsyncMock()
        self.gateway.authorize.side_effect = self.authorize
        self.gateway.retrieve_payment_intent.side_effect = self.retrieve
        self.gateway.cancel.side_effect = self.cancel

    async def authorize(self, **params) -> PaymentIntentResult:
        key = params["idempotency_key"]
        if key not in self.intents:
            self.intents[key] = PaymentIntentResult(
                f"pi_{uuid4().hex}", PaymentIntentStatus.REQUIRES_CAPTURE
            )
        return self.intents[key]

    async def retrieve(self, *, payment_intent_id):
        return next(intent for intent in self.intents.values() if intent.id == payment_intent_id)

    async def cancel(self, *, payment_intent_id, idempotency_key):
        intent = await self.retrieve(payment_intent_id=payment_intent_id)
        cancelled = PaymentIntentResult(intent.id, PaymentIntentStatus.CANCELED)
        for key, existing in self.intents.items():
            if existing.id == intent.id:
                self.intents[key] = cancelled
        return cancelled


@pytest.fixture
async def setup(payments_database: str):
    engine = create_async_engine(payments_database, hide_parameters=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    provider = Provider()
    cards = AsyncMock()
    cards.for_rider.return_value = SavedPaymentCard("cus_fake", "pm_fake")
    worker = HoldWorker(sessions, cards, cast(PaymentGatewayPort, provider.gateway))
    try:
        yield sessions, provider, cards, worker
    finally:
        await engine.dispose()


async def schedule(sessions, event) -> None:
    async with sessions() as session, session.begin():
        await schedule_accepted(event, session)


async def outcomes(sessions, request_id):
    async with sessions() as session:
        rows = await session.execute(
            select(outbox).where(
                outbox.c.envelope["payload"]["requestId"].astext == str(request_id)
            )
        )
        return list(rows.mappings())


async def test_redis_duplicates_and_parallel_workers_hold_saved_amount_once(
    setup, payments_redis: str
) -> None:
    sessions, provider, _cards, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    redis = Redis.from_url(payments_redis, socket_timeout=10)
    try:
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group=f"payments-test-{uuid4()}",
            streams=[stream_name("trips")],
            tables=tables,
        )
        register_hold_handlers(consumer)
        await consumer.ensure_groups()
        for envelope in (event, event, event.model_copy(update={"event_id": uuid4()})):
            await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: envelope.to_json()})
        await consumer.process_once(block_ms=1)
        await asyncio.gather(worker.process(request_id), worker.process(request_id))
        assert len(provider.intents) == 1
        provider.gateway.authorize.assert_awaited_once_with(
            customer_id="cus_fake",
            payment_method_id="pm_fake",
            amount_cents=625,
            currency="CAD",
            idempotency_key=f"hold:{request_id}",
        )
        [held] = await outcomes(sessions, request_id)
        assert held["type"] == "PaymentHeld"
        assert held["envelope"]["payload"]["amountCents"] == 625
        assert held["envelope"]["correlationId"] == event.correlation_id
        provider.gateway.capture.assert_not_awaited()
        async with sessions() as session:
            row = (
                (
                    await session.execute(
                        select(payment_holds).where(payment_holds.c.request_id == request_id)
                    )
                )
                .mappings()
                .one()
            )
            assert row["status"] == HoldStatus.AUTHORIZED.value
            assert row["amount_cents"] == 625
    finally:
        await redis.aclose()


async def test_provider_success_then_database_rollback_reuses_same_key_and_card(
    setup, monkeypatch
) -> None:
    sessions, provider, cards, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    original_save = SQLAlchemyHolds.save
    failed = False

    async def crash_once(self, hold):
        nonlocal failed
        if hold.status is HoldStatus.AUTHORIZED and not failed:
            failed = True
            raise RuntimeError("Simulated database failure after provider success")
        await original_save(self, hold)

    monkeypatch.setattr(SQLAlchemyHolds, "save", crash_once)
    with pytest.raises(RuntimeError, match="database failure"):
        await worker.process(request_id)
    assert await outcomes(sessions, request_id) == []
    cards.for_rider.return_value = SavedPaymentCard("cus_changed", "pm_changed")
    await worker.process(request_id)
    assert len(provider.intents) == 1
    assert (
        provider.gateway.authorize.await_args_list[0]
        == provider.gateway.authorize.await_args_list[1]
    )
    cards.for_rider.assert_awaited_once()
    assert len(await outcomes(sessions, request_id)) == 1


async def test_capture_uses_same_saved_intent_and_duplicate_call_does_not_charge_again(
    setup,
) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    await worker.process(request_id)
    intent = next(iter(provider.intents.values()))
    provider.gateway.capture.return_value = PaymentIntentResult(
        intent.id, PaymentIntentStatus.SUCCEEDED
    )
    result = await worker.capture(request_id)
    await worker.capture(request_id)
    assert result.status is HoldStatus.CAPTURED
    assert result.amount_cents == 625
    provider.gateway.capture.assert_awaited_once_with(
        payment_intent_id=intent.id, idempotency_key=f"capture:{request_id}"
    )


async def test_conflicting_duplicate_cannot_change_saved_price(setup) -> None:
    from payments.application.holds import HoldConflictError

    sessions, _, _, _ = setup
    event = accepted()
    await schedule(sessions, event)
    payload = {**event.payload, "amountCents": 900}
    with pytest.raises(HoldConflictError):
        await schedule(sessions, event.model_copy(update={"event_id": uuid4(), "payload": payload}))


async def test_app_processes_acceptance_using_configured_card_lookup(
    setup, payments_redis: str, payments_database: str, monkeypatch
) -> None:
    from pydantic import SecretStr

    import payments.infrastructure.main as main
    from payments.infrastructure.settings import Settings

    sessions, provider, _, _ = setup
    event = accepted()
    data = event.payload_as(RequestAccepted)
    redis_url = payments_redis.rsplit("/", 1)[0] + "/5"
    settings = Settings(
        _env_file=None,
        database_url=payments_database,
        redis_url=redis_url,
        stripe_secret_key=SecretStr("sk_test_mock"),
        hold_processing_enabled=True,
        saved_card_references={data.rider_id: SavedPaymentCard("cus_configured", "pm_configured")},
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_payment_gateway", lambda settings, client: provider.gateway)
    app = main.create_app()  # No custom lookup injection: exercise the normal settings path.
    redis = Redis.from_url(redis_url)
    try:
        async with app.router.lifespan_context(app):
            await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: event.to_json()})
            async with asyncio.timeout(10):
                for _ in range(200):
                    if await outcomes(sessions, data.request_id):
                        break
                    await asyncio.sleep(0.05)
                else:
                    pytest.fail("Configured hold processor did not publish an outcome")
            provider.gateway.authorize.assert_awaited_once_with(
                customer_id="cus_configured",
                payment_method_id="pm_configured",
                amount_cents=625,
                currency="CAD",
                idempotency_key=f"hold:{data.request_id}",
            )
    finally:
        await redis.aclose()


@pytest.mark.parametrize("case", ["past_departure", "zero_share"])
async def test_new_consumer_group_acknowledges_ineligible_history_without_payment_events(
    setup, payments_redis: str, case: str
) -> None:
    sessions, provider, cards, worker = setup
    event = accepted()
    data = event.payload_as(RequestAccepted)
    payload = dict(event.payload)
    if case == "past_departure":
        payload["departureAt"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    else:
        payload["amountCents"] = 0
    event = event.model_copy(update={"payload": payload})
    redis = Redis.from_url(payments_redis)
    group = f"payments-history-{uuid4()}"
    try:
        # Put the acceptance in the stream BEFORE creating the consumer group.
        await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: event.to_json()})
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group=group,
            streams=[stream_name("trips")],
            tables=tables,
        )
        register_hold_handlers(consumer)
        await consumer.ensure_groups()
        await consumer.process_once(block_ms=1)
        await worker.process(data.request_id)
        async with sessions() as session:
            assert await SQLAlchemyHolds(session).lock(data.request_id) is None
            processed = await session.execute(
                select(tables.processed).where(tables.processed.c.event_id == event.event_id)
            )
            assert processed.first() is not None
            failed = await session.execute(
                select(tables.failed).where(tables.failed.c.event_id == event.event_id)
            )
            assert failed.first() is None
        assert await outcomes(sessions, data.request_id) == []
        cards.for_rider.assert_not_awaited()
        provider.gateway.authorize.assert_not_awaited()
        assert (await redis.xpending(stream_name("trips"), group))["pending"] == 0
    finally:
        await redis.aclose()


def cancellation(event, kind):
    data = event.payload_as(RequestAccepted)
    if kind == "trip":
        payload = TripCancelled(
            trip_id=data.trip_id,
            driver_id=data.driver_id,
            series_id=None,
            departure_at=data.departure_at,
            rider_ids=[data.rider_id],
        )
    else:
        model = RequestCancelled if kind == "cancel" else RequestDeclined
        payload = model(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            driver_id=data.driver_id,
            was_accepted=True,
        )
    return EventEnvelope.wrap(payload, producer="trips", correlation_id=str(uuid4()))


async def deliver_release(sessions, event):
    async with sessions() as session, session.begin():
        await (
            release_trip(event, session)
            if event.type == "TripCancelled"
            else release_request(event, session)
        )


@pytest.mark.parametrize("kind", ["cancel", "decline", "trip"])
async def test_each_cancellation_event_releases_once_with_duplicate_delivery(setup, kind) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    await worker.process(request_id)
    release = cancellation(event, kind)
    await deliver_release(sessions, release)
    await deliver_release(sessions, release.model_copy(update={"event_id": uuid4()}))
    await asyncio.gather(worker.process(request_id), worker.process(request_id))
    await deliver_release(sessions, release)
    await worker.process(request_id)
    rows = await outcomes(sessions, request_id)
    assert [row["type"] for row in rows].count("PaymentReleased") == 1
    [outcome] = [row for row in rows if row["type"] == "PaymentReleased"]
    assert outcome["envelope"]["correlationId"] == release.correlation_id
    provider.gateway.cancel.assert_awaited_once()
    async with sessions() as session:
        assert (await SQLAlchemyHolds(session).lock(request_id)).status is HoldStatus.RELEASED


@pytest.mark.parametrize("kind", ["cancel", "decline", "trip"])
async def test_cancellation_before_acceptance_prevents_future_hold(setup, kind) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await deliver_release(sessions, cancellation(event, kind))
    await schedule(sessions, event)
    await worker.process(request_id)
    provider.gateway.authorize.assert_not_awaited()
    assert await outcomes(sessions, request_id) == []
    async with sessions() as session:
        assert await SQLAlchemyHolds(session).lock(request_id) is None


async def test_scheduled_cancellation_makes_no_provider_request(setup) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    await deliver_release(sessions, cancellation(event, "cancel"))
    await worker.process(request_id)
    provider.gateway.authorize.assert_not_awaited()
    provider.gateway.cancel.assert_not_awaited()
    [row] = await outcomes(sessions, request_id)
    assert row["type"] == "PaymentReleased"


async def test_cancellation_commit_failure_recovers_already_cancelled_intent(
    setup, monkeypatch
) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    await worker.process(request_id)
    await deliver_release(sessions, cancellation(event, "cancel"))
    save = SQLAlchemyHolds.save
    failed = False

    async def crash_once(self, hold):
        nonlocal failed
        if hold.status is HoldStatus.RELEASED and not failed:
            failed = True
            raise RuntimeError("Database failure after cancellation")
        await save(self, hold)

    monkeypatch.setattr(SQLAlchemyHolds, "save", crash_once)
    with pytest.raises(RuntimeError):
        await worker.process(request_id)
    await worker.process(request_id)
    provider.gateway.cancel.assert_awaited_once()
    assert (
        len(
            [
                row
                for row in await outcomes(sessions, request_id)
                if row["type"] == "PaymentReleased"
            ]
        )
        == 1
    )


async def test_trip_cancellation_releases_every_hold_and_blocks_late_riders(setup) -> None:
    sessions, provider, _, worker = setup
    first = accepted()
    a = first.payload_as(RequestAccepted)
    second = first.model_copy(
        update={
            "event_id": uuid4(),
            "payload": {**first.payload, "requestId": str(uuid4()), "riderId": str(uuid4())},
        }
    )
    b = second.payload_as(RequestAccepted)
    await schedule(sessions, first)
    await schedule(sessions, second)
    await worker.process(a.request_id)  # Second hold is still only scheduled.
    await deliver_release(sessions, cancellation(first, "trip"))
    await asyncio.gather(worker.process(a.request_id), worker.process(b.request_id))
    for request_id in (a.request_id, b.request_id):
        assert (
            len(
                [
                    row
                    for row in await outcomes(sessions, request_id)
                    if row["type"] == "PaymentReleased"
                ]
            )
            == 1
        )
    provider.gateway.cancel.assert_awaited_once()
    late = first.model_copy(
        update={
            "event_id": uuid4(),
            "payload": {**first.payload, "requestId": str(uuid4()), "riderId": str(uuid4())},
        }
    )
    await schedule(sessions, late)
    async with sessions() as session:
        assert (
            await SQLAlchemyHolds(session).lock(late.payload_as(RequestAccepted).request_id) is None
        )


async def test_cancel_recovers_authorization_that_succeeded_before_database_failure(
    setup, monkeypatch
) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    save = SQLAlchemyHolds.save

    async def crash_authorization_save(self, hold):
        if hold.status is HoldStatus.AUTHORIZED:
            raise RuntimeError("Lost authorization commit")
        await save(self, hold)

    monkeypatch.setattr(SQLAlchemyHolds, "save", crash_authorization_save)
    with pytest.raises(RuntimeError):
        await worker.process(request_id)
    await deliver_release(sessions, cancellation(event, "cancel"))
    await worker.process(request_id)
    assert len(provider.intents) == 1
    assert next(iter(provider.intents.values())).status is PaymentIntentStatus.CANCELED
    assert (
        provider.gateway.authorize.await_args_list[0]
        == provider.gateway.authorize.await_args_list[1]
    )
    provider.gateway.cancel.assert_awaited_once()
    [outcome] = await outcomes(sessions, request_id)
    assert outcome["type"] == "PaymentReleased"


@pytest.mark.parametrize("kind", ["cancel", "decline", "trip"])
async def test_concurrent_acceptance_scheduling_and_cancellation_do_not_leave_a_hold(
    setup, kind
) -> None:
    sessions, provider, _, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    await asyncio.gather(
        schedule(sessions, event), deliver_release(sessions, cancellation(event, kind))
    )
    await worker.process(request_id)
    provider.gateway.authorize.assert_not_awaited()
    async with sessions() as session:
        hold = await SQLAlchemyHolds(session).lock(request_id)
        assert hold is None or hold.status is HoldStatus.RELEASED


@pytest.mark.parametrize("kind", ["cancel", "decline", "trip"])
@pytest.mark.parametrize("failure", ["declined", "requires_payment_method"])
async def test_cancellation_leaves_failed_hold_unchanged_without_stripe_or_release_event(
    setup, kind: str, failure: str
) -> None:
    sessions, provider, cards, worker = setup
    event = accepted()
    request_id = event.payload_as(RequestAccepted).request_id
    if failure == "declined":
        provider.gateway.authorize.side_effect = PaymentDeclinedError("Card declined")
    else:
        provider.gateway.authorize.side_effect = None
        provider.gateway.authorize.return_value = PaymentIntentResult(
            f"pi_unheld_{uuid4().hex}", PaymentIntentStatus.REQUIRES_PAYMENT_METHOD
        )
    await schedule(sessions, event)
    await worker.process(request_id)
    async with sessions() as session:
        before = await SQLAlchemyHolds(session).lock(request_id)
        assert before.status is HoldStatus.FAILED
        assert (before.stripe_id is None) == (failure == "declined")
    provider.gateway.reset_mock()
    cards.reset_mock()

    await deliver_release(sessions, cancellation(event, kind))
    # An old decline must not be mistaken for an ambiguous authorization needing recovery.
    await worker.process(request_id, now=datetime.now(UTC) + timedelta(days=1))

    async with sessions() as session:
        assert await SQLAlchemyHolds(session).lock(request_id) == before
        assert request_id not in await SQLAlchemyHolds(session).due(
            datetime.now(UTC) + timedelta(days=1)
        )
    assert provider.gateway.mock_calls == []
    cards.for_rider.assert_not_awaited()
    assert [row["type"] for row in await outcomes(sessions, request_id)] == ["PaymentFailed"]


@pytest.mark.parametrize(
    ("lead", "delay"),
    [
        (timedelta(days=6) - timedelta(microseconds=1), timedelta(0)),
        (timedelta(days=6), timedelta(0)),
        (timedelta(days=6, microseconds=1), timedelta(days=5, microseconds=1)),
        (timedelta(days=14), timedelta(days=13)),
    ],
)
async def test_acceptance_persists_authorization_time_at_six_day_boundary(setup, lead, delay):
    sessions, provider, cards, _worker = setup
    event = accepted()
    accepted_at = datetime.now(UTC)
    payload = dict(event.payload)
    payload["departureAt"] = (accepted_at + lead).isoformat()
    event = event.model_copy(update={"payload": payload, "occurred_at": accepted_at})
    data = event.payload_as(RequestAccepted)
    await schedule(sessions, event)
    async with sessions() as session:
        hold = await SQLAlchemyHolds(session).lock(data.request_id)
        assert hold is not None
        assert hold.status is HoldStatus.SCHEDULED
        assert hold.authorize_at == accepted_at + delay
        assert hold.retry_at == hold.authorize_at
        assert hold.first_attempt_at is None
        assert hold.card is None
        due = await SQLAlchemyHolds(session).due(accepted_at)
        assert (data.request_id in due) == (delay == timedelta(0))
    cards.for_rider.assert_not_awaited()
    provider.gateway.authorize.assert_not_awaited()


async def test_delayed_or_republished_acceptance_keeps_original_authorization_schedule(setup):
    sessions, _provider, _cards, _worker = setup
    event = accepted()
    # Accepted a week ago for a trip still five days away: use acceptance time,
    # not the consumer's current clock, to decide whether this was a far-ahead booking.
    accepted_at = datetime.now(UTC) - timedelta(days=7)
    departure = accepted_at + timedelta(days=12)
    payload = dict(event.payload)
    payload["departureAt"] = departure.isoformat()
    event = event.model_copy(update={"payload": payload, "occurred_at": accepted_at})
    data = event.payload_as(RequestAccepted)
    await schedule(sessions, event)
    await schedule(
        sessions,
        event.model_copy(update={"event_id": uuid4(), "occurred_at": datetime.now(UTC)}),
    )
    async with sessions() as session:
        hold = await SQLAlchemyHolds(session).lock(data.request_id)
        assert hold.authorize_at == departure - timedelta(hours=24)
        assert hold.retry_at == hold.authorize_at


@pytest.fixture
async def scheduler_setup(setup):
    # Scheduler passes inspect all holds, so isolate them from other scenarios' pending work.
    sessions, *_ = setup
    async with sessions() as session, session.begin():
        await session.execute(delete(payment_holds))
    return setup


async def test_worker_authorizes_far_ahead_booking_only_when_fake_clock_reaches_due(
    scheduler_setup,
):
    sessions, provider, cards, worker = scheduler_setup
    event = accepted()
    now = datetime.now(UTC)
    payload = dict(event.payload)
    payload["departureAt"] = (now + timedelta(days=14)).isoformat()
    event = event.model_copy(update={"payload": payload, "occurred_at": now})
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    clock = [now]
    worker.clock = lambda: clock[0]
    assert await worker.run_once() == 0
    await worker.process(request_id)  # Even a direct call cannot prepare early.
    cards.for_rider.assert_not_awaited()
    provider.gateway.authorize.assert_not_awaited()
    due = now + timedelta(days=13)
    clock[0] = due - timedelta(microseconds=1)
    assert await worker.run_once() == 0
    clock[0] = due
    assert await worker.run_once() == 1
    assert await worker.run_once() == 0
    provider.gateway.authorize.assert_awaited_once()
    [held] = await outcomes(sessions, request_id)
    assert held["type"] == "PaymentHeld"
    async with sessions() as session:
        hold = await SQLAlchemyHolds(session).lock(request_id)
        assert hold.status is HoldStatus.AUTHORIZED
        assert hold.first_attempt_at == due
        assert hold.amount_cents == 625


async def test_scheduler_skips_locked_hold_and_processes_other_due_work(scheduler_setup):
    sessions, provider, _cards, worker = scheduler_setup
    first, second = accepted(), accepted()
    a = first.payload_as(RequestAccepted).request_id
    b = second.payload_as(RequestAccepted).request_id
    await schedule(sessions, first)
    await schedule(sessions, second)
    async with sessions() as session, session.begin():
        await SQLAlchemyHolds(session).lock(a)
        async with asyncio.timeout(5):
            assert await worker.run_once() == 1
        assert await outcomes(sessions, a) == []
        assert (await outcomes(sessions, b))[0]["type"] == "PaymentHeld"
    assert await worker.run_once() == 1
    assert len(provider.intents) == 2


async def test_scheduler_retires_cancelled_far_ahead_hold_without_stripe(scheduler_setup):
    sessions, provider, cards, worker = scheduler_setup
    event = accepted()
    now = datetime.now(UTC)
    payload = dict(event.payload)
    payload["departureAt"] = (now + timedelta(days=14)).isoformat()
    event = event.model_copy(update={"payload": payload, "occurred_at": now})
    request_id = event.payload_as(RequestAccepted).request_id
    await schedule(sessions, event)
    await deliver_release(sessions, cancellation(event, "cancel"))
    assert await worker.run_once() == 1
    worker.clock = lambda: now + timedelta(days=13)
    assert await worker.run_once() == 0
    cards.for_rider.assert_not_awaited()
    provider.gateway.authorize.assert_not_awaited()
    provider.gateway.cancel.assert_not_awaited()
    [released] = await outcomes(sessions, request_id)
    assert released["type"] == "PaymentReleased"

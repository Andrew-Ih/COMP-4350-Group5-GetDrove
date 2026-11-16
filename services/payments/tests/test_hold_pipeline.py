"""Real consumer/database/outbox tests with an injected, idempotent fake provider."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from events import EventEnvelope, stream_name
from events.catalog import RequestAccepted
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from payments.adapters.hold_events import register_hold_handlers, schedule_accepted
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.adapters.persistence.tables import consumer as tables
from payments.adapters.persistence.tables import outbox, payment_holds
from payments.application.ports import PaymentGatewayPort, PaymentIntentResult, PaymentIntentStatus
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

    async def authorize(self, **params) -> PaymentIntentResult:
        key = params["idempotency_key"]
        if key not in self.intents:
            self.intents[key] = PaymentIntentResult(
                f"pi_{uuid4().hex}", PaymentIntentStatus.REQUIRES_CAPTURE
            )
        return self.intents[key]


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

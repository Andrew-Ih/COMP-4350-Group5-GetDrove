"""Explicit opt-in real Stripe sandbox verification; never run automatically in CI."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from stripe import HTTPXClient, StripeClient

from events import EventEnvelope, stream_name
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.streams import ENVELOPE_FIELD
from payments.adapters.persistence.tables import consumer as consumer_tables
from payments.adapters.persistence.tables import outbox, payment_holds
from payments.infrastructure.settings import Settings


@pytest.mark.skipif(
    os.environ.get("RUN_STRIPE_SANDBOX_HOLD") != "1",
    reason="Opt-in Stripe sandbox test: RUN_STRIPE_SANDBOX_HOLD=1",
)
@pytest.mark.parametrize("release_kind", ["cancel", "decline", "trip"])
async def test_real_sandbox_hold_and_duplicate_acceptance(
    payments_database: str, payments_redis: str, monkeypatch, release_kind: str
) -> None:
    import payments.infrastructure.main as main

    original = Settings()
    if original.stripe_secret_key is None or original.stripe_api_base != "https://api.stripe.com":
        pytest.fail("Configure a Stripe test secret key and remove the mock API override")
    http = HTTPXClient(timeout=10)
    stripe = StripeClient(original.stripe_secret_key.get_secret_value(), http_client=http)
    rider = uuid4()
    request = uuid4()
    customer_id: str | None = None
    redis_url = payments_redis.rsplit("/", 1)[0] + "/6"
    redis = Redis.from_url(redis_url)
    engine = create_async_engine(payments_database, hide_parameters=True, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        customer = await stripe.v1.customers.create_async(
            {"metadata": {"user_id": str(rider), "purpose": "getdrove-task70-smoke"}}
        )
        customer_id = customer.id
        assert customer.livemode is False
        method = await stripe.v1.payment_methods.attach_async(
            "pm_card_visa", {"customer": customer.id}
        )
        settings = original.model_copy(
            update={
                "database_url": payments_database,
                "redis_url": redis_url,
                "hold_processing_enabled": True,
            }
        )
        monkeypatch.setattr(main, "get_settings", lambda: settings)
        event = EventEnvelope.wrap(
            RequestAccepted(
                request_id=request,
                trip_id=uuid4(),
                rider_id=rider,
                driver_id=uuid4(),
                departure_at=datetime.now(UTC) + timedelta(hours=12),
                pickup_label="Sandbox test pickup",
                direction="to_campus",
                amount_cents=625,
                currency="CAD",
                auto_accepted=False,
            ),
            producer="trips",
        )
        from sqlalchemy.dialects.postgresql import insert

        from payments.adapters.persistence.tables import customers

        async with sessions() as session, session.begin():
            await session.execute(
                insert(customers).values(
                    user_id=rider,
                    stripe_customer_id=customer.id,
                    default_payment_method_id=method.id,
                )
            )
        app = main.create_app()
        async with app.router.lifespan_context(app):
            await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: event.to_json()})
            async with asyncio.timeout(45):
                while True:
                    async with sessions() as session:
                        row = (
                            (
                                await session.execute(
                                    select(payment_holds).where(
                                        payment_holds.c.request_id == request
                                    )
                                )
                            )
                            .mappings()
                            .first()
                        )
                    if row and row["status"] == "AUTHORIZED":
                        break
                    if row and row["status"] == "FAILED":
                        pytest.fail("Sandbox authorization failed")
                    await asyncio.sleep(0.1)
            intent = await stripe.v1.payment_intents.retrieve_async(row["stripe_id"])
            assert intent.livemode is False
            assert intent.status == "requires_capture"
            assert intent.capture_method == "manual"
            assert intent.amount == 625
            assert intent.currency == "cad"
            assert intent.amount_received == 0
            duplicate = event.model_copy(update={"event_id": uuid4()})
            for replay in (event, duplicate):
                await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: replay.to_json()})
            async with asyncio.timeout(10):
                for _ in range(100):
                    async with sessions() as session:
                        processed = (
                            await session.execute(
                                select(consumer_tables.processed).where(
                                    consumer_tables.processed.c.event_id.in_(
                                        [event.event_id, duplicate.event_id]
                                    )
                                )
                            )
                        ).all()
                    if len(processed) == 2:
                        break
                    await asyncio.sleep(0.05)
                else:
                    pytest.fail("Duplicate acceptance was not processed")
            # Explicit worker retries must not authorize a completed hold again.
            await asyncio.gather(
                app.state.hold_worker.process(request), app.state.hold_worker.process(request)
            )
            intents = await stripe.v1.payment_intents.list_async({"customer": customer.id})
            assert len(intents.data) == 1 and intents.has_more is False
            async with sessions() as session:
                held = (
                    await session.execute(
                        select(outbox).where(
                            outbox.c.type == "PaymentHeld",
                            outbox.c.envelope["payload"]["requestId"].astext == str(request),
                        )
                    )
                ).all()
                assert len(held) == 1
            print(f"Verified sandbox hold {intent.id}: CAD 6.25, requires_capture, no duplicate")
            data = event.payload_as(RequestAccepted)
            if release_kind == "trip":
                payload = TripCancelled(
                    trip_id=data.trip_id,
                    driver_id=data.driver_id,
                    series_id=None,
                    departure_at=data.departure_at,
                    rider_ids=[rider],
                )
            else:
                model = RequestCancelled if release_kind == "cancel" else RequestDeclined
                payload = model(
                    request_id=request,
                    trip_id=data.trip_id,
                    rider_id=rider,
                    driver_id=data.driver_id,
                    was_accepted=True,
                )
            released_event = EventEnvelope.wrap(payload, producer="trips")
            for replay in (released_event, released_event.model_copy(update={"event_id": uuid4()})):
                await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: replay.to_json()})
            async with asyncio.timeout(45):
                for _ in range(400):
                    async with sessions() as session:
                        row = (
                            (
                                await session.execute(
                                    select(payment_holds).where(
                                        payment_holds.c.request_id == request
                                    )
                                )
                            )
                            .mappings()
                            .one()
                        )
                    if row["status"] == "RELEASED":
                        break
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail("Cancellation did not release the sandbox hold")
            await app.state.hold_worker.process(request)
            cancelled = await stripe.v1.payment_intents.retrieve_async(intent.id)
            assert cancelled.status == "canceled"
            assert cancelled.amount_received == 0
            async with sessions() as session:
                rows = (
                    await session.execute(
                        select(outbox).where(
                            outbox.c.type == "PaymentReleased",
                            outbox.c.envelope["payload"]["requestId"].astext == str(request),
                        )
                    )
                ).all()
                assert len(rows) == 1
            print(f"Verified {release_kind}: {intent.id} canceled, one PaymentReleased, no capture")

    finally:
        # This customer was created exclusively for this test. Leave no test funds held.
        if customer_id is not None:
            intents = await stripe.v1.payment_intents.list_async({"customer": customer_id})
            async for intent in intents.auto_paging_iter():
                if intent.status == "requires_capture":
                    await stripe.v1.payment_intents.cancel_async(intent.id)
        await engine.dispose()
        await redis.aclose()
        await http.close_async()

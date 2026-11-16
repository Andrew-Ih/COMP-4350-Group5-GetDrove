"""Three-service integration belongs in the workspace, never a service's unit tests."""

import os
from dataclasses import replace
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
from events.outbox import OutboxRelay
from events.streams import ENVELOPE_FIELD
from notifications.adapters.events.notification_handlers import register_notification_handlers
from notifications.adapters.persistence.tables import (
    consumer as notification_consumer_tables,
)
from notifications.adapters.persistence.tables import (
    notifications,
)
from notifications.domain.notification_email import Contact
from payments.adapters.hold_events import register_hold_handlers
from payments.adapters.persistence.tables import (
    consumer as payment_consumer_tables,
)
from payments.adapters.persistence.tables import (
    outbox,
    payment_holds,
)
from payments.application.ports import (
    AuthenticationRequiredError,
    PaymentDeclinedError,
    PaymentGatewayPort,
)
from payments.domain.holds import SavedPaymentCard
from payments.infrastructure.hold_worker import HoldWorker
from trips.adapters.payment_events import register_payment_handlers
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import SQLAlchemySeatRequestRepository
from trips.adapters.persistence.tables import consumer as trip_consumer_tables
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote


async def verify_failure(database_url, redis_url, reason, gateway, card):
    engine = create_async_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(redis_url)
    now = datetime.now(UTC)
    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Test area", 49.8, -97.1),
        departure_at=now + timedelta(hours=12),
        duration_seconds=600,
        distance_meters=6000,
        seats_total=3,
    )
    trip.seats_available = 1  # Two accepted riders; failure must give just one seat back.
    request = replace(
        SeatRequest.create(
            trip_id=trip.id,
            rider_id=uuid4(),
            pickup=Location("Test pickup", 49.81, -97.12),
            walk_seconds=120,
            rider_distance_meters=6000,
            detour_seconds=60,
            cost=Quote(270, "CAD", "Saved price"),
            now=now - timedelta(minutes=5),
        ),
        status=RequestStatus.ACCEPTED,
        pickup_order=1,
    )
    other = replace(request, id=uuid4(), rider_id=uuid4(), pickup_order=2)
    contacts = AsyncMock()
    contacts.contacts.return_value = {request.rider_id: Contact("Test rider", "rider@example.test")}
    sender = AsyncMock()
    cards = AsyncMock()
    cards.for_rider.return_value = card
    try:
        async with sessions() as session, session.begin():
            await SQLAlchemyTripRepository(session).add(trip)
            repo = SQLAlchemySeatRequestRepository(session)
            await repo.add(request)
            await repo.add(other)
        accepted = EventEnvelope.wrap(
            RequestAccepted(
                request_id=request.id,
                trip_id=trip.id,
                rider_id=request.rider_id,
                driver_id=trip.driver_id,
                departure_at=trip.departure_at,
                pickup_label=request.pickup.label,
                direction="to_campus",
                amount_cents=270,
                currency="CAD",
                auto_accepted=False,
            ),
            producer="trips",
        )
        payment_consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group=f"payments-failure-{request.id}",
            streams=[stream_name("trips")],
            tables=payment_consumer_tables,
        )
        register_hold_handlers(payment_consumer)
        trips_consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group=f"trips-failure-{request.id}",
            streams=[stream_name("payments")],
            tables=trip_consumer_tables,
        )
        register_payment_handlers(trips_consumer)
        notify_consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group=f"notifications-failure-{request.id}",
            streams=[stream_name("payments")],
            tables=notification_consumer_tables,
        )
        register_notification_handlers(
            notify_consumer, contacts=contacts, sender=sender, web_base_url="http://localhost"
        )
        for consumer in (payment_consumer, trips_consumer, notify_consumer):
            await consumer.ensure_groups()
        await redis.xadd(stream_name("trips"), {ENVELOPE_FIELD: accepted.to_json()})
        await payment_consumer.process_once(block_ms=1)
        worker = HoldWorker(sessions, cards, cast(PaymentGatewayPort, gateway))
        await worker.process(request.id)
        relay = OutboxRelay(
            session_factory=sessions, redis=redis, table=outbox, producer="payments"
        )
        await relay.publish_pending()
        await trips_consumer.process_once(block_ms=1)
        await notify_consumer.process_once(block_ms=1)
        async with sessions() as session:
            failure = (
                (
                    await session.execute(
                        select(outbox).where(
                            outbox.c.type == "PaymentFailed",
                            outbox.c.envelope["payload"]["requestId"].astext == str(request.id),
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert failure["envelope"]["payload"]["reason"] == reason
            assert (
                await session.execute(
                    select(payment_holds.c.status).where(payment_holds.c.request_id == request.id)
                )
            ).scalar_one() == "FAILED"
        # Outbox redelivery preserves the event ID; neither consumer may repeat its effect.
        await redis.xadd(
            stream_name("payments"),
            {ENVELOPE_FIELD: EventEnvelope.model_validate(failure["envelope"]).to_json()},
        )
        await trips_consumer.process_once(block_ms=1)
        await notify_consumer.process_once(block_ms=1)
        async with sessions() as session:
            repo = SQLAlchemySeatRequestRepository(session)
            failed = await repo.get(request.id)
            assert failed.status is RequestStatus.PAYMENT_FAILED
            assert failed.pickup_order is None
            assert failed.cost == request.cost
            assert (await repo.get(other.id)).pickup_order == 1
            available = (
                await session.execute(select(trips.c.seats_available).where(trips.c.id == trip.id))
            ).scalar_one()
            assert available == 2
            rows = (
                (
                    await session.execute(
                        select(notifications).where(notifications.c.request_id == request.id)
                    )
                )
                .mappings()
                .all()
            )
            assert len(rows) == 1
            message = rows[0]
            assert message["type"] == "payment_failed"
            assert "Check your card" in message["body"]
            assert "request the seat again" in message["body"]
            if reason == "card_declined":
                assert "declined" in message["body"]
            else:
                assert "confirm the payment" in message["body"]
        sender.send.assert_awaited_once()
        assert "Check your card" in sender.send.await_args.args[0].text
    finally:
        await redis.aclose()
        await engine.dispose()


@pytest.mark.parametrize("reason", ["card_declined", "authentication_required"])
async def test_payment_failure_returns_seat_and_notifies_rider(
    failure_database, failure_redis, reason
):
    gateway = AsyncMock()
    gateway.authorize.side_effect = (
        PaymentDeclinedError() if reason == "card_declined" else AuthenticationRequiredError()
    )
    # Isolate streams between scenarios; databases retain their own per-event deduplication.
    redis_url = failure_redis.rsplit("/", 1)[0] + ("/1" if reason == "card_declined" else "/2")
    await verify_failure(
        failure_database, redis_url, reason, gateway, SavedPaymentCard("cus_fake", "pm_fake")
    )


@pytest.mark.skipif(
    os.environ.get("RUN_STRIPE_SANDBOX_FAILURE") != "1",
    reason="Opt-in declined-card sandbox test: RUN_STRIPE_SANDBOX_FAILURE=1",
)
async def test_real_declined_card_returns_seat_and_notifies_rider(failure_database, failure_redis):
    from stripe import HTTPXClient, StripeClient

    from payments.adapters.stripe_gateway import StripePaymentGateway
    from payments.infrastructure.settings import Settings

    settings = Settings()
    assert settings.stripe_secret_key is not None
    assert settings.stripe_api_base == "https://api.stripe.com"
    http = HTTPXClient(timeout=10)
    stripe = StripeClient(settings.stripe_secret_key.get_secret_value(), http_client=http)
    customer_id = None
    try:
        customer = await stripe.v1.customers.create_async(
            {"metadata": {"purpose": "getdrove-task153-decline"}}
        )
        customer_id = customer.id
        assert customer.livemode is False
        method = await stripe.v1.payment_methods.attach_async(
            "pm_card_chargeCustomerFail", {"customer": customer.id}
        )
        await verify_failure(
            failure_database,
            failure_redis.rsplit("/", 1)[0] + "/3",
            "card_declined",
            StripePaymentGateway(stripe),
            SavedPaymentCard(customer.id, method.id),
        )
        intents = await stripe.v1.payment_intents.list_async({"customer": customer.id})
        assert len(intents.data) == 1
        assert intents.data[0].amount_received == 0
        assert intents.data[0].status == "requires_payment_method"
        print(
            f"Verified declined sandbox intent {intents.data[0].id}: "
            "failed request, seat returned, rider notified"
        )
    finally:
        if customer_id is not None:
            intents = await stripe.v1.payment_intents.list_async({"customer": customer_id})
            async for intent in intents.auto_paging_iter():
                if intent.status == "requires_capture":
                    await stripe.v1.payment_intents.cancel_async(intent.id)
        await http.close_async()

"""Real database tests for mapping persistence, rollback and concurrent setup."""

import asyncio
from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from payments.adapters.api.cards import CardOperations
from payments.adapters.persistence.tables import customers
from payments.application.ports import PaymentGatewayPort
from payments.domain.cards import SavedCard
from payments.testing import FakeGateway


async def test_concurrent_setup_uses_one_customer_and_persists_default(
    payments_database: str,
) -> None:
    engine = create_async_engine(payments_database, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        gateway = FakeGateway()
        operations = CardOperations(sessions, cast(PaymentGatewayPort, gateway))
        user = uuid4()
        results = await asyncio.gather(*(operations.setup(user) for _ in range(3)))
        assert len(results) == 3
        assert gateway.created == 1
        gateway.cards[f"cus_{user}"] = [SavedCard("pm_new", "visa", "4242", 1, 2031, 12)]
        methods = await operations.methods(user)
        assert methods[0].is_default
        async with sessions() as session:
            row = (
                (await session.execute(select(customers).where(customers.c.user_id == user)))
                .mappings()
                .one()
            )
            assert row["stripe_customer_id"] == f"cus_{user}"
            assert row["default_payment_method_id"] == "pm_new"
        assert await operations.methods(uuid4()) == []
    finally:
        await engine.dispose()


async def test_setup_failure_keeps_mapping_for_retry(payments_database: str) -> None:
    import pytest

    from payments.application.cards import PaymentsUnavailableError

    engine = create_async_engine(payments_database, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        gateway = FakeGateway()
        operations = CardOperations(sessions, cast(PaymentGatewayPort, gateway))
        user = uuid4()
        gateway.fail_setup = True
        with pytest.raises(PaymentsUnavailableError):
            await operations.setup(user)
        gateway.fail_setup = False
        await operations.setup(user)
        assert gateway.created == 1
    finally:
        await engine.dispose()


async def test_card_check_for_unknown_rider_does_not_create_customer(payments_database: str):
    from httpx import ASGITransport, AsyncClient

    from payments.adapters.api.cards import get_card_operations
    from payments.infrastructure.main import create_app

    engine = create_async_engine(payments_database, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        operations = CardOperations(sessions, cast(PaymentGatewayPort, FakeGateway()))
        app = create_app()
        app.dependency_overrides[get_card_operations] = lambda: operations
        user = uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/internal/customers/{user}/card")
        assert response.status_code == 200
        assert response.json() == {"userId": str(user), "hasCard": False}
        async with sessions() as session:
            assert (
                await session.execute(select(customers).where(customers.c.user_id == user))
            ).first() is None
    finally:
        await engine.dispose()


async def test_card_read_releases_connection_before_stripe_and_only_writes_changes(
    payments_database: str,
):
    from sqlalchemy import event

    engine = create_async_engine(payments_database, hide_parameters=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        gateway = FakeGateway()
        operations = CardOperations(sessions, cast(PaymentGatewayPort, gateway))
        user = uuid4()
        await operations.setup(user)
        cards = [SavedCard("pm_latest", "visa", "4242", 1, 2031, 12)]
        writes = []

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def record_writes(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(statement)

        async def list_cards(*, customer_id):
            # No read transaction or pooled connection remains open during Stripe paging.
            assert engine.pool.checkedout() == 0
            async with sessions() as session, session.begin():
                # This fails immediately if the card read still holds the customer lock.
                await session.execute(
                    select(customers)
                    .where(customers.c.user_id == user)
                    .with_for_update(nowait=True)
                )
            return list(cards)

        gateway.list_cards = list_cards
        assert (await operations.methods(user))[0].card.id == "pm_latest"
        assert len(writes) == 1
        assert writes[0].lstrip().upper().startswith("UPDATE")
        writes.clear()
        assert (await operations.methods(user))[0].is_default
        assert writes == []  # The default has not changed.
        cards.clear()
        assert await operations.methods(user) == []
        assert len(writes) == 1  # Removing the last card clears the old default.
        async with sessions() as session:
            assert (
                await session.execute(
                    select(customers.c.default_payment_method_id).where(customers.c.user_id == user)
                )
            ).scalar_one() is None
    finally:
        await engine.dispose()

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

from .card_fakes import FakeGateway


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

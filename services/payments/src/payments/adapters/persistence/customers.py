"""Serialize customer creation per user across workers using a PostgreSQL row lock."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from payments.adapters.persistence.tables import customers
from payments.domain.cards import Customer


class SQLAlchemyCustomers:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock(self, user_id: UUID) -> Customer:
        await self.session.execute(
            insert(customers)
            .values(user_id=user_id)
            .on_conflict_do_nothing(index_elements=[customers.c.user_id])
        )
        result = await self.session.execute(
            select(customers).where(customers.c.user_id == user_id).with_for_update()
        )
        row = result.mappings().one()
        return Customer(user_id, row["stripe_customer_id"], row["default_payment_method_id"])

    async def save(self, customer: Customer) -> None:
        await self.session.execute(
            update(customers)
            .where(customers.c.user_id == customer.user_id)
            .values(
                stripe_customer_id=customer.stripe_customer_id,
                default_payment_method_id=customer.default_payment_method_id,
            )
        )

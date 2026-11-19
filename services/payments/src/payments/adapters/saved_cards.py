"""Resolve hold card references from the customer mapping and Stripe (#428)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payments.adapters.persistence.customers import SQLAlchemyCustomers
from payments.application.cards import Cards
from payments.application.ports import PaymentGatewayPort
from payments.domain.holds import SavedPaymentCard


class CustomerSavedCardLookup:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], gateway: PaymentGatewayPort
    ) -> None:
        self.sessions = sessions
        self.gateway = gateway

    async def for_rider(self, rider_id: UUID) -> SavedPaymentCard | None:
        async with self.sessions() as session:
            customers = SQLAlchemyCustomers(session)
            async with session.begin():
                customer = await customers.get(rider_id)
            if customer is None or customer.stripe_customer_id is None:
                return None
            # Uses #151's newest-card/default rule without a database transaction.
            methods = await Cards(customers, self.gateway).methods(customer)
            default = next((item.card.id for item in methods if item.is_default), None)
            if customer.default_payment_method_id != default:
                async with session.begin():
                    await customers.update_default(customer, default)
            if default is None:
                return None
            return SavedPaymentCard(customer.stripe_customer_id, default)

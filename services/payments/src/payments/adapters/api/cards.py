"""Run card use cases with committed customer mappings and short-lived sessions."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payments.adapters.persistence.customers import SQLAlchemyCustomers
from payments.application.cards import Cards, PaymentsUnavailableError
from payments.application.ports import PaymentGatewayPort, SetupIntentResult
from payments.domain.cards import CardView


class CardOperations:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], gateway: PaymentGatewayPort | None
    ) -> None:
        self.sessions = sessions
        self._gateway = gateway

    @property
    def gateway(self) -> PaymentGatewayPort:
        if self._gateway is None:
            raise PaymentsUnavailableError()
        return self._gateway

    async def setup(self, user_id: UUID) -> SetupIntentResult:
        async with self.sessions() as session:
            cards = Cards(SQLAlchemyCustomers(session), self.gateway)
            async with session.begin():
                customer_id = await cards.ensure_customer(user_id)
            # Keep the mapping even when SetupIntent creation fails.
            return await cards.setup(customer_id)

    async def methods(self, user_id: UUID) -> list[CardView]:
        async with self.sessions() as session, session.begin():
            return await Cards(SQLAlchemyCustomers(session), self.gateway).methods(user_id)


def get_card_operations(request: Request) -> CardOperations:
    return CardOperations(request.app.state.sessions, request.app.state.payment_gateway)


CardService = Annotated[CardOperations, Depends(get_card_operations)]

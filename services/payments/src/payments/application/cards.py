"""Card setup and discovery through provider references, not card data."""

from dataclasses import replace
from uuid import UUID, uuid4

from common_web.errors import DomainError
from payments.application.ports import (
    CustomerRepository,
    PaymentGatewayError,
    PaymentGatewayPort,
    SetupIntentResult,
)
from payments.domain.cards import CardView


class PaymentsUnavailableError(DomainError):
    status = 503
    code = "payments_unavailable"
    title = "Payments are temporarily unavailable"


class Cards:
    def __init__(self, customers: CustomerRepository, gateway: PaymentGatewayPort) -> None:
        self.customers = customers
        self.gateway = gateway

    async def ensure_customer(self, user_id: UUID) -> str:
        customer = await self.customers.lock(user_id)
        if customer.stripe_customer_id is not None:
            return customer.stripe_customer_id
        try:
            customer_id = await self.gateway.create_customer(
                user_id=str(user_id), idempotency_key=f"customer:{user_id}"
            )
        except PaymentGatewayError:
            raise PaymentsUnavailableError() from None
        await self.customers.save(replace(customer, stripe_customer_id=customer_id))
        return customer_id

    async def setup(self, customer_id: str) -> SetupIntentResult:
        try:
            return await self.gateway.create_setup_intent(
                customer_id=customer_id, idempotency_key=f"setup:{uuid4()}"
            )
        except PaymentGatewayError:
            raise PaymentsUnavailableError() from None

    async def methods(self, user_id: UUID) -> list[CardView]:
        customer = await self.customers.lock(user_id)
        if customer.stripe_customer_id is None:
            return []
        try:
            cards = await self.gateway.list_cards(customer_id=customer.stripe_customer_id)
        except PaymentGatewayError:
            raise PaymentsUnavailableError() from None
        # Stripe timestamps have second precision; IDs break ties consistently.
        cards.sort(key=lambda card: (card.created, card.id), reverse=True)
        default_id = cards[0].id if cards else None
        await self.customers.save(replace(customer, default_payment_method_id=default_id))
        return [CardView(card=card, is_default=card.id == default_id) for card in cards]

"""Stateful test doubles for card setup; no Stripe or database calls."""

from uuid import UUID

from payments.application.cards import Cards
from payments.application.ports import PaymentGatewayError, SetupIntentResult
from payments.domain.cards import CardView, Customer, SavedCard


class MemoryCustomers:
    def __init__(self) -> None:
        self.values: dict[UUID, Customer] = {}

    async def lock(self, user_id: UUID) -> Customer:
        return self.values.setdefault(user_id, Customer(user_id, None))

    async def save(self, customer: Customer) -> None:
        self.values[customer.user_id] = customer


class FakeGateway:
    def __init__(self) -> None:
        self.created = 0
        self.cards: dict[str, list[SavedCard]] = {}
        self.fail = False
        self.fail_setup = False
        self.setup_keys: list[str] = []

    async def create_customer(self, *, user_id: str, idempotency_key: str) -> str:
        if self.fail:
            raise PaymentGatewayError("Provider failure")
        self.created += 1
        customer = f"cus_{user_id}"
        self.cards[customer] = []
        return customer

    async def create_setup_intent(
        self, *, customer_id: str, idempotency_key: str
    ) -> SetupIntentResult:
        if self.fail:
            raise PaymentGatewayError("Provider failure")
        if self.fail_setup:
            raise PaymentGatewayError("Setup temporarily unavailable")
        self.setup_keys.append(idempotency_key)
        return SetupIntentResult("seti_test", "seti_test_secret_example")

    async def list_cards(self, *, customer_id: str) -> list[SavedCard]:
        if self.fail:
            raise PaymentGatewayError("Provider failure")
        return list(self.cards[customer_id])


class FakeOperations:
    def __init__(self, cards: Cards) -> None:
        self.cards = cards

    async def setup(self, user_id: UUID) -> SetupIntentResult:
        customer_id = await self.cards.ensure_customer(user_id)
        return await self.cards.setup(customer_id)

    async def methods(self, user_id: UUID) -> list[CardView]:
        return await self.cards.methods(user_id)

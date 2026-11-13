"""Framework-free gateway interface; amounts are integer cents."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SetupIntentResult:
    id: str
    client_secret: str


@dataclass(frozen=True)
class PaymentIntentResult:
    id: str
    status: str


class PaymentGatewayPort(Protocol):
    async def create_customer(self, *, user_id: str, idempotency_key: str) -> str: ...
    async def create_setup_intent(
        self, *, customer_id: str, idempotency_key: str
    ) -> SetupIntentResult: ...
    async def authorize(
        self,
        *,
        customer_id: str,
        payment_method_id: str,
        amount_cents: int,
        currency: str,
        idempotency_key: str,
    ) -> PaymentIntentResult: ...
    async def capture(
        self, *, payment_intent_id: str, idempotency_key: str
    ) -> PaymentIntentResult: ...
    async def cancel(
        self, *, payment_intent_id: str, idempotency_key: str
    ) -> PaymentIntentResult: ...

"""Framework-free gateway interface; amounts are integer cents."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from payments.domain.cards import Customer, SavedCard


class PaymentGatewayError(Exception):
    """A payment provider operation failed."""


class PaymentDeclinedError(PaymentGatewayError):
    """The payment method was declined."""


class AuthenticationRequiredError(PaymentGatewayError):
    """The customer must authenticate before payment can proceed."""


class GatewayUnavailableError(PaymentGatewayError):
    """The provider is temporarily unavailable; retry with the same operation key."""


class PaymentIntentStatus(StrEnum):
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class SetupIntentResult:
    id: str
    client_secret: str


@dataclass(frozen=True)
class PaymentIntentResult:
    id: str
    status: PaymentIntentStatus


class PaymentGatewayPort(Protocol):
    """Operations raise PaymentGatewayError subclasses, never provider SDK errors."""

    async def create_customer(self, *, user_id: str, idempotency_key: str) -> str: ...
    async def create_setup_intent(
        self, *, customer_id: str, idempotency_key: str
    ) -> SetupIntentResult: ...
    async def list_cards(self, *, customer_id: str) -> list[SavedCard]: ...
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


class CustomerRepository(Protocol):
    async def lock(self, user_id: UUID) -> Customer:
        """Ensure a row exists and lock it until the caller's transaction ends."""
        ...

    async def save(self, customer: Customer) -> None: ...

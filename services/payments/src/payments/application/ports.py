"""Framework-free gateway interface; amounts are integer cents."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from payments.domain.cards import Customer, SavedCard
from payments.domain.holds import FailureReason, PaymentHold, SavedPaymentCard


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
    async def retrieve_payment_intent(self, *, payment_intent_id: str) -> PaymentIntentResult: ...

    async def cancel(
        self, *, payment_intent_id: str, idempotency_key: str
    ) -> PaymentIntentResult: ...


class CustomerRepository(Protocol):
    async def lock(self, user_id: UUID) -> Customer:
        """Ensure a row exists and lock it until the caller's transaction ends."""
        ...

    async def save(self, customer: Customer) -> None: ...


class SavedCardLookup(Protocol):
    async def for_rider(self, rider_id: UUID) -> SavedPaymentCard | None:
        """Return the saved references, None for no card; raise on lookup failure.

        Production integration follows #151. Configuration failures must not be
        reported as a rider having no card.
        """
        ...


class HoldRepository(Protocol):
    async def schedule(self, hold: PaymentHold) -> None: ...
    async def lock(self, request_id: UUID) -> PaymentHold | None: ...
    async def save(self, hold: PaymentHold) -> None: ...
    async def due(self, now: datetime, limit: int = 20) -> list[UUID]: ...

    async def request_release(
        self,
        request_id: UUID,
        trip_id: UUID,
        rider_id: UUID,
        driver_id: UUID,
        correlation_id: str | None,
        now: datetime,
    ) -> None: ...

    async def release_trip(
        self, trip_id: UUID, driver_id: UUID, correlation_id: str | None, now: datetime
    ) -> None: ...


class HoldEvents(Protocol):
    async def held(self, hold: PaymentHold) -> None: ...

    async def released(self, hold: PaymentHold) -> None: ...
    async def failed(self, hold: PaymentHold, reason: FailureReason) -> None: ...

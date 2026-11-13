"""Async Stripe adapter translating provider failures into application errors."""

from collections.abc import Iterator
from contextlib import contextmanager

from stripe import (
    APIConnectionError,
    APIError,
    CardError,
    RateLimitError,
    StripeClient,
    StripeError,
)

from payments.application.ports import (
    AuthenticationRequiredError,
    GatewayUnavailableError,
    PaymentDeclinedError,
    PaymentGatewayError,
    PaymentIntentResult,
    PaymentIntentStatus,
    SetupIntentResult,
)
from payments.domain.cards import SavedCard


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except StripeError as exc:
        if exc.code == "authentication_required":
            raise AuthenticationRequiredError("Customer authentication is required") from exc
        if isinstance(exc, CardError):
            raise PaymentDeclinedError("Payment method was declined") from exc
        if isinstance(exc, (APIConnectionError, APIError, RateLimitError)):
            raise GatewayUnavailableError("Payment provider is temporarily unavailable") from exc
        raise PaymentGatewayError("Payment provider operation failed") from exc


class StripePaymentGateway:
    def __init__(self, client: StripeClient) -> None:
        self._client = client

    async def list_cards(self, *, customer_id: str) -> list[SavedCard]:
        cards: list[SavedCard] = []
        with _translate_errors():
            methods = await self._client.v1.payment_methods.list_async(
                {"customer": customer_id, "type": "card", "limit": 100}
            )
            async for method in methods.auto_paging_iter():
                if method.card is not None:
                    cards.append(
                        SavedCard(
                            id=method.id,
                            brand=method.card.brand,
                            last4=method.card.last4,
                            exp_month=method.card.exp_month,
                            exp_year=method.card.exp_year,
                            created=method.created,
                        )
                    )
        return cards

    async def create_customer(self, *, user_id: str, idempotency_key: str) -> str:
        with _translate_errors():
            customer = await self._client.v1.customers.create_async(
                {"metadata": {"user_id": user_id}}, options={"idempotency_key": idempotency_key}
            )
        return customer.id

    async def create_setup_intent(
        self, *, customer_id: str, idempotency_key: str
    ) -> SetupIntentResult:
        with _translate_errors():
            intent = await self._client.v1.setup_intents.create_async(
                {"customer": customer_id, "payment_method_types": ["card"], "usage": "off_session"},
                options={"idempotency_key": idempotency_key},
            )
        if intent.client_secret is None:
            raise RuntimeError("Stripe returned a SetupIntent without a client secret")
        return SetupIntentResult(id=intent.id, client_secret=intent.client_secret)

    async def authorize(
        self,
        *,
        customer_id: str,
        payment_method_id: str,
        amount_cents: int,
        currency: str,
        idempotency_key: str,
    ) -> PaymentIntentResult:
        if amount_cents <= 0:
            raise ValueError("Authorization amount must be positive")
        with _translate_errors():
            intent = await self._client.v1.payment_intents.create_async(
                {
                    "customer": customer_id,
                    "payment_method": payment_method_id,
                    "amount": amount_cents,
                    "currency": currency.lower(),
                    "capture_method": "manual",
                    "confirm": True,
                    "off_session": True,
                    "payment_method_types": ["card"],
                },
                options={"idempotency_key": idempotency_key},
            )
        return PaymentIntentResult(id=intent.id, status=PaymentIntentStatus(intent.status))

    async def capture(self, *, payment_intent_id: str, idempotency_key: str) -> PaymentIntentResult:
        with _translate_errors():
            intent = await self._client.v1.payment_intents.capture_async(
                payment_intent_id, options={"idempotency_key": idempotency_key}
            )
        return PaymentIntentResult(id=intent.id, status=PaymentIntentStatus(intent.status))

    async def cancel(self, *, payment_intent_id: str, idempotency_key: str) -> PaymentIntentResult:
        with _translate_errors():
            intent = await self._client.v1.payment_intents.cancel_async(
                payment_intent_id, options={"idempotency_key": idempotency_key}
            )
        return PaymentIntentResult(id=intent.id, status=PaymentIntentStatus(intent.status))

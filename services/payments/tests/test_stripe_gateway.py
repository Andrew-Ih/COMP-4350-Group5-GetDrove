"""Exercise real SDK serialization without reaching Stripe."""

import json
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from stripe import HTTPXClient, StripeClient

from payments.adapters.stripe_gateway import StripePaymentGateway
from payments.application.ports import (
    AuthenticationRequiredError,
    GatewayUnavailableError,
    PaymentDeclinedError,
    PaymentGatewayError,
    PaymentIntentStatus,
)
from payments.infrastructure.gateway import create_payment_gateway
from payments.infrastructure.settings import Settings


async def test_gateway_requests() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/customers":
            data = {"id": "cus_test", "object": "customer"}
        elif request.url.path == "/v1/setup_intents":
            data = {"id": "seti_test", "object": "setup_intent", "client_secret": "test_secret"}
        else:
            data = {"id": "pi_test", "object": "payment_intent", "status": "requires_capture"}
        return httpx.Response(200, content=json.dumps(data))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        gateway = StripePaymentGateway(
            StripeClient(
                "sk_test_mock",
                http_client=HTTPXClient(_lib=SimpleNamespace(AsyncClient=lambda **kwargs: http)),
            )
        )
        assert (
            await gateway.create_customer(user_id="user-1", idempotency_key="customer-1")
            == "cus_test"
        )
        setup = await gateway.create_setup_intent(customer_id="cus_test", idempotency_key="setup-1")
        assert setup.client_secret == "test_secret"  # noqa: S105 - mock response, not a credential
        hold = await gateway.authorize(
            customer_id="cus_test",
            payment_method_id="pm_test",
            amount_cents=450,
            currency="CAD",
            idempotency_key="hold-1",
        )
        assert hold.status is PaymentIntentStatus.REQUIRES_CAPTURE
        await gateway.capture(payment_intent_id=hold.id, idempotency_key="capture-1")
        await gateway.cancel(payment_intent_id=hold.id, idempotency_key="cancel-1")
        with pytest.raises(ValueError, match="positive"):
            await gateway.authorize(
                customer_id="cus_test",
                payment_method_id="pm_test",
                amount_cents=0,
                currency="CAD",
                idempotency_key="invalid",
            )

    assert [r.url.path for r in requests] == [
        "/v1/customers",
        "/v1/setup_intents",
        "/v1/payment_intents",
        "/v1/payment_intents/pi_test/capture",
        "/v1/payment_intents/pi_test/cancel",
    ]
    assert [r.headers["Idempotency-Key"] for r in requests] == [
        "customer-1",
        "setup-1",
        "hold-1",
        "capture-1",
        "cancel-1",
    ]
    params = parse_qs(requests[2].content.decode())
    assert params["capture_method"] == ["manual"]
    assert params["off_session"] == ["true"]
    assert params["confirm"] == ["true"]
    assert params["amount"] == ["450"]
    assert params["currency"] == ["cad"]
    assert parse_qs(requests[1].content.decode())["usage"] == ["off_session"]


def test_reject_live_keys_and_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYMENTS_STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stripe_secret_key=SecretStr("sk_live_invalid"))
    with pytest.raises(ValueError, match="required"):
        create_payment_gateway(Settings(_env_file=None))


@pytest.mark.parametrize(
    "operation", ["customer", "setup", "authorize", "capture", "cancel", "list_cards"]
)
@pytest.mark.parametrize(
    ("status", "error_type", "code", "expected"),
    [
        (402, "card_error", "card_declined", PaymentDeclinedError),
        (402, "card_error", "authentication_required", AuthenticationRequiredError),
        (500, "api_error", "api_error", GatewayUnavailableError),
        (429, "rate_limit_error", "rate_limit", GatewayUnavailableError),
        (401, "invalid_request_error", "invalid_api_key", PaymentGatewayError),
        (400, "invalid_request_error", "parameter_missing", PaymentGatewayError),
        (0, "", "", GatewayUnavailableError),
    ],
)
async def test_gateway_translates_sdk_errors(
    operation: str, status: int, error_type: str, code: str, expected: type[PaymentGatewayError]
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if status == 0:
            raise httpx.ConnectError("Connection failed", request=request)
        return httpx.Response(
            status,
            json={"error": {"type": error_type, "code": code, "message": "Provider failure"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        gateway = StripePaymentGateway(
            StripeClient(
                "sk_test_mock",
                max_network_retries=0,
                http_client=HTTPXClient(_lib=SimpleNamespace(AsyncClient=lambda **kwargs: http)),
            )
        )
        with pytest.raises(expected) as caught:
            match operation:
                case "list_cards":
                    await gateway.list_cards(customer_id="cus_test")
                case "customer":
                    await gateway.create_customer(user_id="user-1", idempotency_key="customer-1")
                case "setup":
                    await gateway.create_setup_intent(
                        customer_id="cus_test", idempotency_key="setup-1"
                    )
                case "authorize":
                    await gateway.authorize(
                        customer_id="cus_test",
                        payment_method_id="pm_test",
                        amount_cents=450,
                        currency="CAD",
                        idempotency_key="hold-1",
                    )
                case "capture":
                    await gateway.capture(payment_intent_id="pi_test", idempotency_key="capture-1")
                case "cancel":
                    await gateway.cancel(payment_intent_id="pi_test", idempotency_key="cancel-1")
        assert type(caught.value) is expected
        assert caught.value.__cause__ is not None


async def test_list_cards_follows_pages_and_returns_only_safe_fields() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = 2 if "starting_after" in request.url.params else 1
        method = {
            "id": f"pm_{page}",
            "object": "payment_method",
            "created": page,
            "type": "card",
            "card": {
                "brand": "visa",
                "last4": "4242",
                "exp_month": 12,
                "exp_year": 2030,
                "fingerprint": "provider-only",
            },
        }
        return httpx.Response(
            200,
            json={
                "object": "list",
                "url": "/v1/payment_methods",
                "data": [method],
                "has_more": page == 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        gateway = StripePaymentGateway(
            StripeClient(
                "sk_test_mock",
                http_client=HTTPXClient(_lib=SimpleNamespace(AsyncClient=lambda **kwargs: http)),
            )
        )
        cards = await gateway.list_cards(customer_id="cus_owner")
    assert [card.id for card in cards] == ["pm_1", "pm_2"]
    assert len(requests) == 2
    assert all(request.url.params["customer"] == "cus_owner" for request in requests)
    assert all(request.url.params["type"] == "card" for request in requests)
    assert requests[1].url.params["starting_after"] == "pm_1"
    assert all(not hasattr(card, "fingerprint") for card in cards)

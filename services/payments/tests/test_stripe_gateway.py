"""Exercise real SDK serialization without reaching Stripe."""

import json
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from stripe import HTTPXClient, StripeClient

from payments.adapters.stripe_gateway import StripePaymentGateway
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
        assert hold.status == "requires_capture"
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

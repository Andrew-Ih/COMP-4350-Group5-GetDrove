"""Card endpoints: authentication, ownership, defaults and provider failures."""

from typing import cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from payments.adapters.api.cards import get_card_operations
from payments.application.cards import Cards
from payments.application.ports import PaymentGatewayPort
from payments.domain.cards import SavedCard
from payments.infrastructure.main import create_app

from .card_fakes import FakeGateway, FakeOperations, MemoryCustomers


@pytest.fixture
def harness():
    customers = MemoryCustomers()
    gateway = FakeGateway()
    operations = FakeOperations(Cards(customers, cast(PaymentGatewayPort, gateway)))
    app = create_app()
    app.dependency_overrides[get_card_operations] = lambda: operations
    auth = TestAuth()
    auth.install(app)
    return app, auth, customers, gateway


async def test_setup_reuses_customer_and_returns_only_client_secret(harness) -> None:
    app, auth, customers, gateway = harness
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            response = await client.post("/setup-intent", headers=auth.headers())
            assert response.status_code == 201
            assert response.json() == {"clientSecret": "seti_test_secret_example"}
    assert gateway.created == 1
    assert customers.values[auth.user_id].stripe_customer_id == f"cus_{auth.user_id}"
    assert len(set(gateway.setup_keys)) == 2


async def test_methods_refresh_after_setup_and_do_not_leak_between_users(harness) -> None:
    app, auth, customers, gateway = harness
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/methods", headers=auth.headers())).json() == []
        await client.post("/setup-intent", headers=auth.headers())
        assert (await client.get(f"/internal/customers/{auth.user_id}/card")).json()[
            "hasCard"
        ] is False
        gateway.cards[f"cus_{auth.user_id}"] = [
            SavedCard("pm_old", "visa", "4242", 12, 2030, 1),
            SavedCard("pm_new", "mastercard", "4444", 1, 2031, 2),
        ]
        response = await client.get("/methods", headers=auth.headers())
        assert response.status_code == 200
        assert response.json() == [
            {
                "id": "pm_new",
                "brand": "mastercard",
                "last4": "4444",
                "expMonth": 1,
                "expYear": 2031,
                "isDefault": True,
            },
            {
                "id": "pm_old",
                "brand": "visa",
                "last4": "4242",
                "expMonth": 12,
                "expYear": 2030,
                "isDefault": False,
            },
        ]
        assert customers.values[auth.user_id].default_payment_method_id == "pm_new"
        assert (await client.get(f"/internal/customers/{auth.user_id}/card")).json() == {
            "userId": str(auth.user_id),
            "hasCard": True,
        }
        other = uuid4()
        assert (await client.get("/methods", headers=auth.headers(user_id=other))).json() == []
        assert (await client.get(f"/internal/customers/{other}/card")).json()["hasCard"] is False
        assert gateway.created == 1
        gateway.cards[f"cus_{auth.user_id}"] = []
        assert (await client.get("/methods", headers=auth.headers())).json() == []
        assert customers.values[auth.user_id].default_payment_method_id is None


@pytest.mark.parametrize(("method", "path"), [("POST", "/setup-intent"), ("GET", "/methods")])
async def test_authentication_required_before_card_operations(harness, method, path) -> None:
    app, _, customers, gateway = harness
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 401
    assert gateway.created == 0
    assert customers.values == {}


@pytest.mark.parametrize("operation", ["setup", "methods", "internal"])
async def test_provider_failure_returns_contract_error(harness, operation) -> None:
    app, auth, _, gateway = harness
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/setup-intent", headers=auth.headers())
        gateway.fail = True
        if operation == "setup":
            response = await client.post("/setup-intent", headers=auth.headers())
        else:
            path = (
                "/methods" if operation == "methods" else f"/internal/customers/{auth.user_id}/card"
            )
            response = await client.get(path, headers=auth.headers())
    assert response.status_code == 503
    assert response.json()["code"] == "payments_unavailable"
    assert "Provider failure" not in response.text


async def test_missing_key_keeps_health_auth_and_uuid_validation_working(monkeypatch) -> None:
    import payments.infrastructure.main as main
    from payments.infrastructure.settings import Settings

    monkeypatch.setattr(
        main, "get_settings", lambda: Settings(_env_file=None, stripe_secret_key=None)
    )
    app = main.create_app()
    auth = TestAuth()
    auth.install(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/methods")).status_code == 401
        assert (await client.get("/internal/customers/not-a-uuid/card")).status_code == 422
        response = await client.get("/methods", headers=auth.headers())
        assert response.status_code == 503
        assert response.json()["code"] == "payments_unavailable"

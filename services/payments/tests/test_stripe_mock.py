"""Schema smoke test against a throwaway stripe-mock container (no real keys)."""

from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from payments.infrastructure.gateway import create_payment_gateway
from payments.infrastructure.settings import Settings


@pytest.fixture(scope="module")
def stripe_mock_url() -> Iterator[str]:
    import docker

    try:
        docker.from_env().ping()
    except docker.errors.DockerException:
        pytest.skip("Docker is not running; start Docker Desktop for the stripe-mock test")
    # Keep the mock schema compatible with stripe-python 14's parameter names.
    with (
        DockerContainer("stripe/stripe-mock:v0.197.0")
        .with_exposed_ports(12111)
        .waiting_for(LogMessageWaitStrategy("Listening for HTTP")) as container
    ):
        yield f"http://{container.get_container_host_ip()}:{container.get_exposed_port(12111)}"


async def test_customer_and_setup_intent(stripe_mock_url: str) -> None:
    gateway = create_payment_gateway(
        Settings(
            _env_file=None,
            stripe_secret_key=SecretStr("sk_test_mock"),
            stripe_api_base=stripe_mock_url,
        )
    )
    customer = await gateway.create_customer(user_id="test-user", idempotency_key="test-customer")
    intent = await gateway.create_setup_intent(customer_id=customer, idempotency_key="test-setup")
    assert customer.startswith("cus_")
    assert intent.id.startswith("seti_")
    assert intent.client_secret


async def test_card_endpoints_against_stripe_mock(
    stripe_mock_url: str, payments_database: str
) -> None:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from common_security.testing import TestAuth
    from payments.adapters.api.cards import CardOperations, get_card_operations
    from payments.infrastructure.main import create_app

    engine = create_async_engine(payments_database, hide_parameters=True)
    try:
        gateway = create_payment_gateway(
            Settings(
                _env_file=None,
                stripe_secret_key=SecretStr("sk_test_mock"),
                stripe_api_base=stripe_mock_url,
            )
        )
        operations = CardOperations(async_sessionmaker(engine, expire_on_commit=False), gateway)
        app = create_app()
        app.dependency_overrides[get_card_operations] = lambda: operations
        auth = TestAuth()
        auth.install(app)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            setup = await client.post("/setup-intent", headers=auth.headers())
            assert setup.status_code == 201
            assert setup.json()["clientSecret"].startswith("seti_")
            methods = await client.get("/methods", headers=auth.headers())
            assert methods.status_code == 200
            assert methods.json()
            assert all(
                set(card) == {"id", "brand", "last4", "expMonth", "expYear", "isDefault"}
                for card in methods.json()
            )
            assert sum(card["isDefault"] for card in methods.json()) == 1
            status = await client.get(f"/internal/customers/{auth.user_id}/card")
            assert status.json() == {"userId": str(auth.user_id), "hasCard": True}
    finally:
        await engine.dispose()

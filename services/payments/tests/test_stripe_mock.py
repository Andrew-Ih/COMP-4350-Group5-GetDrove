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

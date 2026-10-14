"""The Payments API contract (#108)."""

from httpx import ASGITransport, AsyncClient

from payments.infrastructure.main import create_app


def test_spec_documents_the_quote_endpoint() -> None:
    assert "/internal/quotes" in create_app().openapi()["paths"]


async def test_valid_quote_request_reaches_the_not_yet_implemented_handler() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post("/internal/quotes", json={"distanceMeters": 9300})

    assert response.status_code == 501


async def test_negative_distance_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post("/internal/quotes", json={"distanceMeters": -1})

    assert response.status_code == 422

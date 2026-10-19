"""The Payments API contract (#108)."""

from httpx import ASGITransport, AsyncClient

from payments.adapters.api.payments_router import PricingConfig, get_pricing_config
from payments.infrastructure.main import create_app


def test_spec_documents_the_quote_endpoint() -> None:
    assert "/internal/quotes" in create_app().openapi()["paths"]


async def test_valid_quote_request_returns_quote() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/quotes",
            json={"distanceMeters": 9300},
        )

    assert response.status_code == 200
    assert response.json() == {
        "amountCents": 420,
        "currency": "CAD",
        "explanation": "9.3 km at $0.45/km",
    }


async def test_negative_distance_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post("/internal/quotes", json={"distanceMeters": -1})

    assert response.status_code == 422


def test_every_error_response_has_its_own_example() -> None:
    """#230: errors used to share one example from the Problem schema, so the docs showed
    the same body for every error. Each one now shows its own status and code."""
    for path, operations in create_app().openapi()["paths"].items():
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                if not status.isdigit() or int(status) < 400:
                    continue
                content = response["content"]["application/json"]
                where = f"{method.upper()} {path} {status}"
                assert content["schema"] == {"$ref": "#/components/schemas/Problem"}, where
                example = content["example"]
                assert example["status"] == int(status), where
                assert f"`{example['code']}" in response["description"], where


async def test_zero_distance_returns_minimum_quote() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/quotes",
            json={"distanceMeters": 0},
        )

    assert response.status_code == 200
    assert response.json() == {
        "amountCents": 200,
        "currency": "CAD",
        "explanation": "0 km at $0.45/km ($2.00 minimum)",
    }


async def test_distance_above_maximum_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/quotes",
            json={"distanceMeters": 200_001},
        )

    assert response.status_code == 422


async def test_explanation_uses_one_decimal_place() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/quotes",
            json={"distanceMeters": 12345},
        )

    assert response.status_code == 200
    assert response.json()["explanation"] == "12.3 km at $0.45/km"


async def test_custom_rate_updates_price_and_explanation() -> None:
    app = create_app()

    app.dependency_overrides[get_pricing_config] = lambda: PricingConfig(
        rate_cents_per_km=50,
        minimum_fare_cents=200,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/quotes",
            json={"distanceMeters": 6000},
        )

    assert response.status_code == 200
    assert response.json() == {
        "amountCents": 300,
        "currency": "CAD",
        "explanation": "6 km at $0.50/km",
    }

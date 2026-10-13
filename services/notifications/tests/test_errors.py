from httpx import ASGITransport, AsyncClient

from notifications.infrastructure.main import create_app


async def test_unknown_route_returns_problem_details() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/no/such/route", headers={"X-Request-ID": "req-1"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["x-request-id"] == "req-1"
    assert response.json()["code"] == "not_found"

"""Error responses and request IDs, through a small FastAPI app."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from common_web import ConflictError, InvalidField, InvalidInputError, NotFoundError
from common_web.app import install


class NoSeatsLeftError(ConflictError):
    code = "no_seats_left"
    title = "No seats left"


class TripIn(BaseModel):
    seats_total: int = Field(alias="seatsTotal", ge=1, le=6)


def make_app() -> FastAPI:
    app = FastAPI()
    install(app, service="test")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/trips/{trip_id}")
    async def get_trip(trip_id: str) -> dict[str, str]:
        raise NotFoundError(f"Trip {trip_id} doesn't exist")

    @app.post("/trips/{trip_id}/requests")
    async def request_seat(trip_id: str) -> None:
        raise NoSeatsLeftError("No seats left on this trip")

    @app.post("/trips")
    async def post_trip(body: TripIn) -> dict[str, int]:
        return {"seatsTotal": body.seats_total}

    @app.post("/check")
    async def check() -> None:
        raise InvalidInputError(
            "Departure is in the past", [InvalidField("departureAt", "Must be in the future")]
        )

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    return app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=make_app(), raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_domain_error_becomes_problem_details(client: AsyncClient) -> None:
    response = await client.post("/trips/abc/requests")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "No seats left"
    assert body["status"] == 409
    assert body["detail"] == "No seats left on this trip"
    assert body["instance"] == "/trips/abc/requests"
    assert body["code"] == "no_seats_left"
    assert body["requestId"] == response.headers["x-request-id"]


async def test_not_found_error(client: AsyncClient) -> None:
    response = await client.get("/trips/abc")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["detail"] == "Trip abc doesn't exist"


async def test_validation_errors_list_the_bad_fields(client: AsyncClient) -> None:
    response = await client.post("/trips", json={"seatsTotal": 9})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_input"
    assert [error["field"] for error in body["errors"]] == ["seatsTotal"]


async def test_invalid_input_error_from_domain_lists_fields(client: AsyncClient) -> None:
    response = await client.post("/check")

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "departureAt", "message": "Must be in the future"}
    ]


async def test_unknown_route_is_problem_details(client: AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "not_found"


async def test_wrong_method_is_problem_details(client: AsyncClient) -> None:
    response = await client.delete("/trips")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert "allow" in response.headers


async def test_unexpected_error_hides_internals(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = await client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert "hunter2" not in response.text
    assert body["requestId"] == response.headers["x-request-id"]
    assert any("hunter2" in record.getMessage() or record.exc_info for record in caplog.records)


async def test_incoming_request_id_is_reused(client: AsyncClient) -> None:
    response = await client.get("/trips/abc", headers={"X-Request-ID": "req-123"})

    assert response.headers["x-request-id"] == "req-123"
    assert response.json()["requestId"] == "req-123"


async def test_missing_request_id_is_generated(client: AsyncClient) -> None:
    first = await client.get("/health")
    second = await client.get("/health")

    assert first.headers["x-request-id"]
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


async def test_unsafe_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id with spaces"})

    assert response.headers["x-request-id"] != "bad id with spaces"
    assert " " not in response.headers["x-request-id"]


async def test_each_request_is_logged_with_its_id(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="common_web.requests"):
        await client.get("/trips/abc", headers={"X-Request-ID": "req-456"})
        await client.get("/health")

    request_logs = [r for r in caplog.records if r.name == "common_web.requests"]
    assert len(request_logs) == 1  # /health isn't logged
    record = request_logs[0]
    assert record.status == 404  # type: ignore[attr-defined]
    assert record.path == "/trips/abc"  # type: ignore[attr-defined]
    assert record.request_id == "req-456"  # type: ignore[attr-defined]
    assert record.service == "test"  # type: ignore[attr-defined]

"""Trips' saved-card lookup against the Payments HTTP contract."""

from uuid import uuid4

import httpx
import pytest

from trips.adapters.payments import HTTPRiderCardService
from trips.domain.request_errors import CardStatusUnavailableError


@pytest.mark.parametrize("has_card", [True, False])
async def test_returns_card_status_for_the_requested_rider(has_card: bool) -> None:
    rider_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/internal/customers/{rider_id}/card"
        return httpx.Response(
            200,
            json={"userId": str(rider_id), "hasCard": has_card},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://payments:8000",
    ) as client:
        result = await HTTPRiderCardService(client).has_card(rider_id)

    assert result is has_card


@pytest.mark.parametrize("status", [404, 422, 500, 501, 503])
async def test_http_errors_are_not_treated_as_no_card(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://payments:8000",
    ) as client:
        with pytest.raises(CardStatusUnavailableError):
            await HTTPRiderCardService(client).has_card(uuid4())


async def test_timeout_is_not_treated_as_no_card() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Payments timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://payments:8000",
    ) as client:
        with pytest.raises(CardStatusUnavailableError):
            await HTTPRiderCardService(client).has_card(uuid4())


@pytest.mark.parametrize(
    "case",
    [
        "invalid-json",
        "missing-user",
        "missing-status",
        "wrong-user",
        "string-status",
        "integer-status",
        "null-status",
    ],
)
async def test_invalid_response_is_rejected(case: str) -> None:
    rider_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "missing-user":
            return httpx.Response(200, json={"hasCard": True})
        if case == "missing-status":
            return httpx.Response(200, json={"userId": str(rider_id)})
        if case == "wrong-user":
            return httpx.Response(
                200,
                json={"userId": str(uuid4()), "hasCard": True},
            )
        if case == "string-status":
            return httpx.Response(
                200,
                json={"userId": str(rider_id), "hasCard": "false"},
            )
        if case == "integer-status":
            return httpx.Response(
                200,
                json={"userId": str(rider_id), "hasCard": 1},
            )
        return httpx.Response(
            200,
            json={"userId": str(rider_id), "hasCard": None},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://payments:8000",
    ) as client:
        with pytest.raises(CardStatusUnavailableError):
            await HTTPRiderCardService(client).has_card(rider_id)

"""The contract for a series' first departure (#315): it must be on one of the chosen
weekdays, judged by its Winnipeg day, so the driver gets exactly the days they picked."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import get_post_recurring_trip
from trips.adapters.api.schemas import PostTripSeriesRequest
from trips.infrastructure.main import create_app

SERIES: dict[str, Any] = {
    "direction": "to_campus",
    "place": {"label": "Wolseley Ave & Arlington St", "lat": 49.8794, "lng": -97.1663},
    "departureAt": "2026-11-16T13:10:00Z",  # Monday 7:10 in Winnipeg
    "seatsTotal": 3,
    "weekdays": ["mon", "wed", "fri"],
    "endDate": "2026-12-11",
}


@pytest.fixture
async def client() -> AsyncClient:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    app.dependency_overrides[get_post_recurring_trip] = object

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(),
    )


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"weekdays": ["wed", "mon"]},
        # Tuesday 01:30 UTC is still Monday evening in Winnipeg.
        {"departureAt": "2026-11-17T01:30:00Z", "weekdays": ["mon"]},
    ],
)
def test_a_first_departure_on_a_chosen_weekday_is_valid(change: dict[str, Any]) -> None:
    PostTripSeriesRequest.model_validate({**SERIES, **change})


@pytest.mark.parametrize("end_date", ["2026-11-15", "2026-11-16", "2027-03-09"])
async def test_invalid_end_date_identifies_the_field(client: AsyncClient, end_date: str) -> None:
    response = await client.post("/series", json={**SERIES, "endDate": end_date})

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_input"
    assert [error["field"] for error in body["errors"]] == ["endDate"]


@pytest.mark.parametrize(
    "change",
    [
        {"weekdays": ["tue", "wed"]},
        # Monday evening in Winnipeg, even though it's Tuesday in UTC.
        {"departureAt": "2026-11-17T01:30:00Z", "weekdays": ["tue"]},
        # Saturday in Winnipeg can never be a chosen weekday.
        {"departureAt": "2026-11-21T14:00:00Z"},
    ],
)
async def test_a_first_departure_on_another_day_is_rejected(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    response = await client.post("/series", json={**SERIES, **change})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_input"
    assert [error["field"] for error in body["errors"]] == ["weekdays"]


def test_spec_documents_the_rule() -> None:
    weekdays = PostTripSeriesRequest.model_json_schema(by_alias=True)["properties"]["weekdays"]

    assert "first departure must be on one of them" in weekdays["description"]

"""Accounts adapter against Accounts' HTTP contract."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from trips.adapters.accounts import HTTPDriverVehicleService, HTTPRiderProfileService
from trips.application.ports import DriverVehicle, RiderProfile
from trips.domain.request_errors import AccountsUnavailableError

type Handler = Callable[[httpx.Request], httpx.Response]


def user(user_id: UUID, **changes: Any) -> dict[str, Any]:
    return {
        "id": str(user_id),
        "firstName": "Priya",
        "rating": 4.5,
        "ratingCount": 8,
        "tripCount": 12,
        "noShowCount": 1,
        "vehicle": None,
        **changes,
    }


def echo(calls: list[list[str]]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/users"
        ids = request.url.params.get_list("ids")
        calls.append(ids)
        return httpx.Response(200, json={"users": [user(UUID(i)) for i in ids]})

    return handler


async def lookup(handler: Handler, ids: list[UUID]) -> dict[UUID, RiderProfile]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://accounts:8000"
    ) as client:
        return await HTTPRiderProfileService(client).get_many(ids)


async def test_all_riders_are_loaded_in_one_call() -> None:
    calls: list[list[str]] = []
    first, second = uuid4(), uuid4()

    profiles = await lookup(echo(calls), [first, second])

    assert calls == [[str(first), str(second)]]
    assert profiles[first] == RiderProfile(
        id=first, first_name="Priya", rating=4.5, rating_count=8, no_show_count=1
    )
    assert set(profiles) == {first, second}


async def test_a_rider_is_asked_for_once() -> None:
    calls: list[list[str]] = []
    rider = uuid4()

    await lookup(echo(calls), [rider, rider])

    assert calls == [[str(rider)]]


async def test_no_riders_means_no_call() -> None:
    calls: list[list[str]] = []

    assert await lookup(echo(calls), []) == {}
    assert calls == []


async def test_more_than_fifty_riders_are_split_into_batches() -> None:
    calls: list[list[str]] = []
    riders = [uuid4() for _ in range(51)]

    profiles = await lookup(echo(calls), riders)

    assert [len(call) for call in calls] == [50, 1]
    assert set(profiles) == set(riders)


async def test_unknown_riders_are_left_out() -> None:
    known, unknown = uuid4(), uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"users": [user(known)]})

    profiles = await lookup(handler, [known, unknown])

    assert set(profiles) == {known}


async def test_a_rider_with_no_ratings_has_a_null_rating() -> None:
    rider = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"users": [user(rider, rating=None, ratingCount=0, noShowCount=0)]}
        )

    profiles = await lookup(handler, [rider])

    assert profiles[rider].rating is None


@pytest.mark.parametrize(
    "failure",
    ["timeout", "connect-error", "http-error", "no-content", "invalid-json", "invalid-fields"],
)
async def test_accounts_failures_are_reported(failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("Accounts timed out", request=request)
        if failure == "connect-error":
            raise httpx.ConnectError("Accounts is down", request=request)
        if failure == "http-error":
            return httpx.Response(503)
        if failure == "no-content":
            return httpx.Response(204)
        if failure == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        return httpx.Response(200, json={"users": [{"id": "nope"}]})

    with pytest.raises(AccountsUnavailableError):
        await lookup(handler, [uuid4()])


# ---------------------------------------------------------------- drivers' vehicles (#361)

CIVIC = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"}


async def vehicle_of(driver: UUID, handler: Handler) -> DriverVehicle | None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://accounts:8000"
    ) as client:
        return await HTTPDriverVehicleService(client).get_vehicle(driver)


async def test_a_drivers_vehicle_comes_with_its_plate() -> None:
    driver, asked = uuid4(), []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params.get_list("ids"))
        return httpx.Response(200, json={"users": [user(driver, vehicle=CIVIC)]})

    assert await vehicle_of(driver, handler) == DriverVehicle("Honda", "Civic", "Blue", "ABC123")
    assert asked == [[str(driver)]]


@pytest.mark.parametrize("users", [[], "no vehicle"])
async def test_no_vehicle_or_unknown_driver_is_none(users: Any) -> None:
    driver = uuid4()
    body = {"users": [user(driver)] if users == "no vehicle" else users}

    assert await vehicle_of(driver, lambda request: httpx.Response(200, json=body)) is None


def down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Accounts is down", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(501),  # what Accounts answers until #143 is deployed
        lambda request: httpx.Response(503),
        lambda request: httpx.Response(200, content=b"not JSON"),
        down,
    ],
    ids=["501", "503", "invalid-json", "connect-error"],
)
async def test_accounts_not_answering_about_a_vehicle_is_reported(handler: Handler) -> None:
    with pytest.raises(AccountsUnavailableError):
        await vehicle_of(uuid4(), handler)

"""Private locations never reach anyone else, a log or the database's error messages (#31).

Two locations pass through Trips: the rider's, on every search (used for matching only, never
stored), and the driver's own place, usually near home, when a trip is posted (stored, but
only ever shown to that driver). These tests prove neither is in another user's response or
in any log line.
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.tables import outbox, trips
from trips.infrastructure.database import create_database_engine
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

# Digits that appear nowhere else in the test: if one shows up, that location leaked.
RIDER = {"lat": 49.852713, "lng": -97.179137}
RIDER_DIGITS = ("852713", "179137")
DRIVER_PLACE = {"label": "Driver's own street", "lat": 49.876541, "lng": -97.143219}
DRIVER_DIGITS = ("876541", "143219", "Driver's own street")


def leaks(text_: str, digits: tuple[str, ...]) -> list[str]:
    return [d for d in digits if d in text_]


class API:
    def __init__(self, app: FastAPI, auth: TestAuth) -> None:
        self.app, self.auth = app, auth
        self.driver, self.rider = uuid4(), uuid4()


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    # The engine the service creates, so the tests cover its settings too.
    engine = create_database_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    api = API(app, auth)
    try:
        yield api
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(api.driver)
                    )
                )
                await connection.execute(delete(trips).where(trips.c.driver_id == api.driver))
        finally:
            await engine.dispose()


def routing(request: httpx.Request) -> httpx.Response:
    """Routing: computes the route when posting; on search, every candidate matches, with a
    pickup on the route (nowhere near the rider's exact spot or the driver's place)."""
    body = json.loads(request.content)
    if request.url.path == "/internal/routes":
        return httpx.Response(
            200, json={"tripId": body["tripId"], "distanceMeters": 8800, "durationSeconds": 800}
        )
    pickup = {"label": "Pembina Highway", "lat": 49.84, "lng": -97.15}
    matches = [
        {"tripId": t, "pickup": pickup, "walkSeconds": 240, "riderDistanceMeters": 4000}
        for t in body["tripIds"]
    ]
    return httpx.Response(200, json={"matches": matches})


def payments(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"amountCents": 200, "currency": "CAD", "explanation": "4.0 km at $0.45/km"}
    )


async def call(api: API, method: str, path: str, user: UUID, **kwargs: Any) -> httpx.Response:
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(routing), base_url="http://routing:8000"
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(payments), base_url="http://payments:8000"
        ) as payments_client,
    ):
        api.app.state.routing_client = routing_client
        api.app.state.payments_client = payments_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False),
            base_url="http://test",
            headers={**api.auth.headers(user_id=user), "X-Request-ID": str(api.driver)},
        ) as client:
            return await client.request(method, path, **kwargs)


async def post_and_search(api: API) -> tuple[httpx.Response, httpx.Response]:
    departure = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
    posted = await call(
        api,
        "POST",
        "/",
        api.driver,
        json={
            "direction": "to_campus",
            "place": DRIVER_PLACE,
            "departureAt": departure.isoformat(),
            "seatsTotal": 3,
        },
    )
    searched = await call(
        api,
        "GET",
        "/search",
        api.rider,
        params={
            **RIDER,
            "direction": "to_campus",
            "time": (departure + timedelta(hours=1)).isoformat(),
        },
    )
    return posted, searched


# ---------------------------------------------------------------- responses


async def test_search_results_never_show_the_drivers_place_or_echo_the_riders(api: API) -> None:
    posted, searched = await post_and_search(api)

    assert posted.status_code == 201, posted.text
    assert searched.status_code == 200, searched.text
    [result] = [r for r in searched.json() if r["trip"]["id"] == posted.json()["id"]]
    assert result["trip"]["origin"] is None  # the driver's end, going to campus
    assert leaks(searched.text, DRIVER_DIGITS) == []
    assert leaks(searched.text, RIDER_DIGITS) == []


async def test_the_driver_does_see_their_own_place(api: API) -> None:
    """The rule is about other people: the driver's own trip still shows where they start."""
    posted, _ = await post_and_search(api)

    assert posted.json()["origin"] == DRIVER_PLACE


# ---------------------------------------------------------------- logs


async def test_posting_and_searching_log_neither_location(
    api: API, caplog: pytest.LogCaptureFixture
) -> None:
    """Every logger, at every level: the request log (the search's query string holds the
    rider's location), httpx's calls to Routing and Payments, SQLAlchemy."""
    with caplog.at_level(logging.DEBUG):
        posted, searched = await post_and_search(api)

    assert (posted.status_code, searched.status_code) == (201, 200)
    assert caplog.records
    assert leaks(caplog.text, RIDER_DIGITS + DRIVER_DIGITS) == []


async def test_the_service_engine_doesnt_list_query_parameters_in_errors() -> None:
    """SQLAlchemy normally adds a failed query's parameters to its error message; the
    service's engine doesn't. The driver's own message can still quote a value, which is why
    the logs also take coordinates out (common_web.logs, and the logging tests above)."""
    query = text("SELECT CAST(:place AS integer)")
    place = {"place": f"{DRIVER_PLACE['lat']},{DRIVER_PLACE['lng']}"}

    plain = create_async_engine(get_settings().database_url)
    service = create_database_engine(get_settings().database_url)
    try:
        for engine, lists_them in ((plain, True), (service, False)):
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError) as error:
                    await connection.execute(query, place)
            message = str(error.value)
            assert ("[parameters:" in message) is lists_them
            assert ("SQL parameters hidden" in message) is not lists_them
    finally:
        await plain.dispose()
        await service.dispose()

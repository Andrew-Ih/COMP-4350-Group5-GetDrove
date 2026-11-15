"""A rider's location never reaches anyone else, a log or the database's error messages (#31).

Routing gets the rider's exact location on every search and pickup request. It's used for the
calculation only: these tests prove it isn't in the responses (pickups are points on the
driver's route) or in any log line, including when the database fails mid-search.
"""

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import Corridor, Direction, LatLng
from routing.infrastructure.database import create_database_engine
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("routing_database")

type Handler = Callable[[httpx.Request], httpx.Response]

# The rider's location, with digits that appear nowhere else in the test: if any of these
# strings shows up in a response or a log, the location leaked.
RIDER = {"lat": 49.852713, "lng": -97.179137}
RIDER_DIGITS = ("852713", "179137")

WEST, EAST = LatLng(lat=49.85, lng=-97.20), LatLng(lat=49.85, lng=-97.158)


def leaks(text_: str) -> list[str]:
    return [digits for digits in RIDER_DIGITS if digits in text_]


class API:
    def __init__(self, app: FastAPI, engine: AsyncEngine, route: Route) -> None:
        self.app, self.engine, self.route = app, engine, route


@pytest.fixture
async def api() -> AsyncIterator[API]:
    app = create_app()
    # The engine the service creates, so the tests cover its settings too.
    engine = create_database_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.corridor = Corridor(radius_meters=800)
    app.state.max_walk_seconds = 600
    route = Route(
        trip_id=uuid4(),
        path=(WEST, EAST),
        distance_meters=round(distance_meters(WEST, EAST)),
        duration_seconds=300,
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
    )
    try:
        async with app.state.session_factory() as session, session.begin():
            await SQLAlchemyRouteRepository(session).save(route, sample_route(route))
        yield API(app, engine, route)
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(routes).where(routes.c.trip_id == route.trip_id))
        finally:
            await engine.dispose()


def foot(request: httpx.Request) -> httpx.Response:
    """OSRM's table service: walking 1.3 times the straight-line distance, at 5 km/h."""
    coordinates = request.url.path.removeprefix("/table/v1/foot/").split(";")
    rider, *destinations = (
        LatLng(lat=float(lat), lng=float(lng)) for lng, lat in (c.split(",") for c in coordinates)
    )
    meters = [0.0] + [distance_meters(rider, d) * 1.3 for d in destinations]
    return httpx.Response(
        200,
        json={"code": "Ok", "durations": [[m / 1.39 for m in meters]], "distances": [meters]},
    )


def car(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"code": "Ok", "waypoints": [{"name": "Pembina Highway", "distance": 5}]}
    )


async def post(api: API, path: str, body: dict[str, Any]) -> httpx.Response:
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(foot), base_url="http://osrm-foot:5000"
        ) as foot_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(car), base_url="http://osrm-car:5000"
        ) as car_client,
    ):
        api.app.state.osrm_foot_client = foot_client
        api.app.state.osrm_car_client = car_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post(path, json=body)


def requests_with_the_riders_location(api: API) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("/internal/matches", {"rider": RIDER, "tripIds": [str(api.route.trip_id)]}),
        ("/internal/pickup-points", {"tripId": str(api.route.trip_id), "rider": RIDER}),
    ]


# ---------------------------------------------------------------- responses


async def test_responses_never_contain_the_riders_location(api: API) -> None:
    for path, body in requests_with_the_riders_location(api):
        response = await post(api, path, body)

        assert response.status_code == 200, response.text
        assert response.json() != {"matches": []}, path  # the rider did match
        assert leaks(response.text) == [], path


# ---------------------------------------------------------------- logs


async def test_requests_log_nothing_of_the_riders_location(
    api: API, caplog: pytest.LogCaptureFixture
) -> None:
    """Every logger, at every level: the request log, httpx's calls to OSRM (whose URLs hold
    the coordinates), SQLAlchemy."""
    with caplog.at_level(logging.DEBUG):
        for path, body in requests_with_the_riders_location(api):
            assert (await post(api, path, body)).status_code == 200

    assert caplog.records  # the requests were logged
    assert leaks(caplog.text) == []


async def test_a_database_failure_mid_search_logs_nothing_of_the_riders_location(
    api: API, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected error is logged with its traceback, and a database error's message
    normally includes the query's parameters: here, the rider's location."""

    async def failing_search(self: SQLAlchemyRouteRepository, rider: LatLng, *args: object) -> None:
        # A query with the rider's location as a parameter, that the database rejects.
        await self.session.execute(
            text("SELECT CAST(:rider AS integer)"), {"rider": f"POINT({rider.lng} {rider.lat})"}
        )

    monkeypatch.setattr(SQLAlchemyRouteRepository, "samples_in_corridor", failing_search)

    with caplog.at_level(logging.DEBUG):
        response = await post(api, *requests_with_the_riders_location(api)[0])

    assert response.status_code == 500
    assert "Unhandled error" in caplog.text  # the traceback was logged
    assert leaks(caplog.text) == []


async def test_the_service_engine_doesnt_list_query_parameters_in_errors() -> None:
    """SQLAlchemy normally adds a failed query's parameters to its error message; the
    service's engine doesn't. The driver's own message can still quote a value, which is why
    the logs also take coordinates out (common_web.logs, and the logging tests above)."""
    query, rider = text("SELECT CAST(:rider AS integer)"), {"rider": "POINT(-97.179137 49.852713)"}

    plain = create_async_engine(get_settings().database_url)
    service = create_database_engine(get_settings().database_url)
    try:
        for engine, lists_them in ((plain, True), (service, False)):
            async with engine.connect() as connection:
                with pytest.raises(DBAPIError) as error:
                    await connection.execute(query, rider)
            message = str(error.value)
            assert ("[parameters:" in message) is lists_them
            assert ("SQL parameters hidden" in message) is not lists_them
    finally:
        await plain.dispose()
        await service.dispose()

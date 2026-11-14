"""GET /{trip_id} with a real PostgreSQL database and mocked Routing and Payments (#30)."""

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location
from trips.infrastructure.database import create_database_engine
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type Handler = Callable[[httpx.Request], httpx.Response]

TIME = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
RIDER = {"lat": 49.85, "lng": -97.15}
# The driver's own end of the trip: never shown to anyone else.
HOME = Location("Driver's home street", 49.82, -97.15)

# Routing's points for this rider, best first, as both its endpoints would give them.
POINTS = [
    {
        "id": "s12",
        "label": "Pembina Highway",
        "lat": 49.84,
        "lng": -97.15,
        "walk": 120,
        "toEnd": 9000,
    },
    {
        "id": "s15",
        "label": "Pembina Highway",
        "lat": 49.837,
        "lng": -97.15,
        "walk": 300,
        "toEnd": 8700,
    },
    {"id": "s18", "label": "Point Road", "lat": 49.834, "lng": -97.149, "walk": 420, "toEnd": 8400},
]


class API:
    def __init__(self, app: FastAPI, auth: TestAuth) -> None:
        self.app, self.auth = app, auth
        self.driver = uuid4()
        self.routing_requests: list[httpx.Request] = []
        self.trips: list[Trip] = []

    async def add(self, direction: Direction = Direction.TO_CAMPUS) -> Trip:
        trip = Trip.create(
            driver_id=self.driver,
            direction=direction,
            place=HOME,
            departure_at=TIME,
            duration_seconds=900,
            distance_meters=12000,  # a 12 km trip, so the points' prices differ
            seats_total=3,
        )
        async with self.app.state.session_factory() as session, session.begin():
            await SQLAlchemyTripRepository(session).add(trip)
        self.trips.append(trip)
        return trip

    async def get(
        self,
        path: str,
        params: Any = None,
        headers: dict[str, str] | None = None,
        routing: "Handler | None" = None,
        payments: "Handler | None" = None,
    ) -> httpx.Response:
        handler = routing or routing_service

        def recording(request: httpx.Request) -> httpx.Response:
            self.routing_requests.append(request)
            return handler(request)

        async with (
            httpx.AsyncClient(
                transport=httpx.MockTransport(recording), base_url="http://routing:8000"
            ) as routing_client,
            httpx.AsyncClient(
                transport=httpx.MockTransport(payments or payments_service),
                base_url="http://payments:8000",
            ) as payments_client,
        ):
            self.app.state.routing_client = routing_client
            self.app.state.payments_client = payments_client
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
                base_url="http://test",
                headers=self.auth.headers(user_id=uuid4()) if headers is None else headers,
            ) as client:
                return await client.get(path, params=params)


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_database_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    api = API(app, auth)
    try:
        yield api
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(trips).where(trips.c.driver_id == api.driver))
        finally:
            await engine.dispose()


def routing_service(request: httpx.Request) -> httpx.Response:
    """Routing: the pickup points, and search's matches, from the same points, as Routing's
    own rules guarantee (its first pickup point is search's)."""
    body = json.loads(request.content)
    if request.url.path == "/internal/pickup-points":
        offered = [p for p in POINTS if p["id"] not in body["exclude"]][: body["limit"]]
        return httpx.Response(
            200,
            json={
                "pickups": [
                    {
                        "id": p["id"],
                        "label": p["label"],
                        "lat": p["lat"],
                        "lng": p["lng"],
                        "walkSeconds": p["walk"],
                        "riderDistanceMeters": p["toEnd"],
                    }
                    for p in offered
                ]
            },
        )
    best = POINTS[0]
    matches = [
        {
            "tripId": trip_id,
            "pickup": {"label": best["label"], "lat": best["lat"], "lng": best["lng"]},
            "walkSeconds": best["walk"],
            "riderDistanceMeters": best["toEnd"],
        }
        for trip_id in body["tripIds"]
    ]
    return httpx.Response(200, json={"matches": matches})


def payments_service(request: httpx.Request) -> httpx.Response:
    distance = json.loads(request.content)["distanceMeters"]
    return httpx.Response(
        200,
        json={
            "amountCents": max(200, round(distance * 0.045 / 5) * 5),
            "currency": "CAD",
            "explanation": f"{distance / 1000:.1f} km at $0.45/km",
        },
    )


def pickup_requests(api: API) -> list[dict[str, Any]]:
    return [
        json.loads(r.content)
        for r in api.routing_requests
        if r.url.path == "/internal/pickup-points"
    ]


async def test_a_rider_gets_the_trip_with_its_pickup_points(api: API) -> None:
    trip = await api.add()

    response = await api.get(f"/{trip.id}", params=RIDER)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trip"]["id"] == str(trip.id)
    # The driver's own end is hidden; the campus end is shown.
    assert body["trip"]["origin"] is None
    assert body["trip"]["destination"]["label"] == "University of Manitoba, Fort Garry campus"
    assert HOME.label not in response.text
    assert body["pickups"] == [
        {
            "id": "s12",
            "label": "Pembina Highway",
            "lat": 49.84,
            "lng": -97.15,
            "walkSeconds": 120,
            "cost": {"amountCents": 405, "currency": "CAD", "explanation": "9.0 km at $0.45/km"},
        },
        {
            "id": "s15",
            "label": "Pembina Highway",
            "lat": 49.837,
            "lng": -97.15,
            "walkSeconds": 300,
            "cost": {"amountCents": 390, "currency": "CAD", "explanation": "8.7 km at $0.45/km"},
        },
        {
            "id": "s18",
            "label": "Point Road",
            "lat": 49.834,
            "lng": -97.149,
            "walkSeconds": 420,
            "cost": {"amountCents": 380, "currency": "CAD", "explanation": "8.4 km at $0.45/km"},
        },
    ]
    # Not built yet: they come with seat requests (#34).
    assert (body["vehicle"], body["myRequest"]) == (None, None)
    [sent] = pickup_requests(api)
    assert (sent["tripId"], sent["rider"], sent["limit"]) == (str(trip.id), RIDER, 3)


async def test_the_first_point_and_its_cost_match_what_search_showed(api: API) -> None:
    """#30: the trip detail and search agree for the same trip and spot."""
    trip = await api.add()
    # Leaves at TIME and arrives 15 minutes later: arriving by TIME + 30 min finds it.
    arrive_by = (TIME + timedelta(minutes=30)).isoformat()
    search_params = {**RIDER, "direction": "to_campus", "time": arrive_by}

    searched = (await api.get("/search", params=search_params)).json()
    detail = (await api.get(f"/{trip.id}", params=RIDER)).json()

    [result] = [r for r in searched if r["trip"]["id"] == str(trip.id)]
    first = detail["pickups"][0]
    assert {k: first[k] for k in ("label", "lat", "lng", "walkSeconds")} == result["pickup"]
    assert first["cost"] == result["cost"]


async def test_rejected_points_are_left_out_and_the_next_come_back(api: API) -> None:
    trip = await api.add()

    response = await api.get(f"/{trip.id}", params={**RIDER, "exclude": ["s12", "s15"]})

    assert [p["id"] for p in response.json()["pickups"]] == ["s18"]
    assert pickup_requests(api)[0]["exclude"] == ["s12", "s15"]


async def test_the_driver_sees_their_own_end_and_no_pickups(api: API) -> None:
    trip = await api.add()

    response = await api.get(
        f"/{trip.id}", params=RIDER, headers=api.auth.headers(user_id=api.driver)
    )

    assert response.status_code == 200, response.text
    assert response.json()["trip"]["origin"]["label"] == HOME.label
    assert response.json()["pickups"] == []
    assert api.routing_requests == []


async def test_leaving_campus_the_drivers_end_is_hidden_too(api: API) -> None:
    trip = await api.add(Direction.FROM_CAMPUS)

    body = (await api.get(f"/{trip.id}", params=RIDER)).json()

    assert body["trip"]["destination"] is None
    assert body["trip"]["origin"]["label"] == "University of Manitoba, Fort Garry campus"


async def test_without_a_location_there_are_no_pickups(api: API) -> None:
    trip = await api.add()

    response = await api.get(f"/{trip.id}")

    assert response.status_code == 200, response.text
    assert response.json()["pickups"] == []
    assert api.routing_requests == []


async def test_a_trip_without_a_route_has_no_pickups(api: API) -> None:
    trip = await api.add()

    def no_route(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": "route_not_found"})

    response = await api.get(f"/{trip.id}", params=RIDER, routing=no_route)

    assert response.status_code == 200, response.text
    assert response.json()["pickups"] == []


async def test_payments_down_still_shows_the_points_without_a_cost(api: API) -> None:
    trip = await api.add()

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": "service_unavailable"})

    response = await api.get(f"/{trip.id}", params=RIDER, payments=down)

    assert response.status_code == 200, response.text
    assert [p["cost"] for p in response.json()["pickups"]] == [None, None, None]


async def test_routing_down_returns_503(api: API) -> None:
    trip = await api.add()

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Routing is down", request=request)

    response = await api.get(f"/{trip.id}", params=RIDER, routing=down)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_unavailable"


async def test_an_unknown_trip_returns_404(api: API) -> None:
    response = await api.get(f"/{uuid4()}", params=RIDER)

    assert response.status_code == 404
    assert response.json()["code"] == "trip_not_found"
    assert api.routing_requests == []


async def test_requires_a_login(api: API) -> None:
    trip = await api.add()

    response = await api.get(f"/{trip.id}", headers={})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"

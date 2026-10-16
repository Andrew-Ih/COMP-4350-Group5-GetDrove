"""Integration tests for the POST /trips endpoint."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.tables import trips
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings


@pytest.mark.asyncio
async def test_post_trip_returns_201_and_saves_trip() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    engine = create_async_engine(get_settings().database_url)

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                app.state.session_factory = async_sessionmaker(
                    connection,
                    expire_on_commit=False,
                )

                def routing_handler(
                    request: httpx.Request,
                ) -> httpx.Response:
                    assert request.method == "POST"
                    assert request.url.path == "/internal/routes"

                    payload = json.loads(request.content)
                    assert payload["origin"]["lat"] == 49.82
                    assert payload["destination"]["lat"] == 49.8075

                    return httpx.Response(
                        200,
                        json={
                            "tripId": payload["tripId"],
                            "distanceMeters": 6000,
                            "durationSeconds": 900,
                        },
                    )

                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(routing_handler),
                    base_url="http://routing:8000",
                ) as routing_client:
                    app.state.routing_client = routing_client

                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app),
                        base_url="http://test",
                        headers=auth.headers(),
                    ) as client:
                        response = await client.post(
                            "/",
                            json={
                                "direction": "to_campus",
                                "place": {
                                    "label": "Pembina Highway",
                                    "lat": 49.82,
                                    "lng": -97.15,
                                },
                                "departureAt": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                                "seatsTotal": 3,
                            },
                        )

                assert response.status_code == 201, response.text

                body = response.json()
                assert body["driverId"] == str(auth.user_id)
                assert body["distanceMeters"] == 6000
                assert body["durationSeconds"] == 900
                assert body["seatsAvailable"] == 3
                assert body["status"] == "scheduled"

                result = await connection.execute(select(trips).where(trips.c.id == body["id"]))
                assert result.mappings().one()["driver_id"] == auth.user_id

            finally:
                await transaction.rollback()

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_post_trip_rejects_past_departure() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    routing_called = False

    def routing_handler(request: httpx.Request) -> httpx.Response:
        nonlocal routing_called
        routing_called = True
        return httpx.Response(200, json={})

    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(routing_handler),
            base_url="http://routing:8000",
        ) as routing_client:
            app.state.routing_client = routing_client

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers=auth.headers(),
            ) as client:
                response = await client.post(
                    "/",
                    json={
                        "direction": "to_campus",
                        "place": {
                            "label": "Pembina Highway",
                            "lat": 49.82,
                            "lng": -97.15,
                        },
                        "departureAt": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                        "seatsTotal": 3,
                    },
                )

        assert response.status_code == 422
        assert response.json()["code"] == "departure_in_past"
        assert routing_called is False

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_post_trip_returns_503_when_routing_fails() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    def routing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(routing_handler),
            base_url="http://routing:8000",
        ) as routing_client:
            app.state.routing_client = routing_client

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers=auth.headers(),
            ) as client:
                response = await client.post(
                    "/",
                    json={
                        "direction": "to_campus",
                        "place": {
                            "label": "Pembina Highway",
                            "lat": 49.82,
                            "lng": -97.15,
                        },
                        "departureAt": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                        "seatsTotal": 3,
                    },
                )

        assert response.status_code == 503
        assert response.json()["code"] == "routing_unavailable"

    finally:
        await engine.dispose()

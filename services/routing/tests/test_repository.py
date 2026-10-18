"""Integration tests for the Routing repository (real PostgreSQL + PostGIS)."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.domain.entities import Route
from routing.domain.values import LatLng
from routing.infrastructure.settings import get_settings

HOME = LatLng(lat=49.82, lng=-97.15)
CAMPUS = LatLng(lat=49.8075, lng=-97.1366)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with AsyncSession(engine) as session:
            yield session
            # No commit: closing the session rolls back test data.
    finally:
        await engine.dispose()


async def saved(session: AsyncSession, trip_id: UUID) -> RowMapping:
    result = await session.execute(
        select(
            routes.c.distance_meters,
            routes.c.duration_seconds,
            func.ST_AsText(routes.c.path).label("wkt"),
            func.ST_SRID(routes.c.path).label("srid"),
        ).where(routes.c.trip_id == trip_id)
    )
    return result.mappings().one()


async def test_save_stores_the_route_as_a_linestring(session: AsyncSession) -> None:
    route = Route(
        trip_id=uuid4(),
        path=(HOME, LatLng(lat=49.815, lng=-97.14), CAMPUS),
        distance_meters=6000,
        duration_seconds=900,
    )

    await SQLAlchemyRouteRepository(session).save(route)

    row = await saved(session, route.trip_id)
    assert row["wkt"] == "LINESTRING(-97.15 49.82,-97.14 49.815,-97.1366 49.8075)"
    assert row["srid"] == 4326
    assert row["distance_meters"] == 6000
    assert row["duration_seconds"] == 900


async def test_save_again_replaces_the_route(session: AsyncSession) -> None:
    repository = SQLAlchemyRouteRepository(session)
    trip_id = uuid4()

    await repository.save(
        Route(trip_id=trip_id, path=(HOME, CAMPUS), distance_meters=6000, duration_seconds=900)
    )
    await repository.save(
        Route(trip_id=trip_id, path=(CAMPUS, HOME), distance_meters=6500, duration_seconds=960)
    )

    count = await session.scalar(
        select(func.count()).select_from(routes).where(routes.c.trip_id == trip_id)
    )
    assert count == 1
    row = await saved(session, trip_id)
    assert row["wkt"] == "LINESTRING(-97.1366 49.8075,-97.15 49.82)"
    assert row["distance_meters"] == 6500
    assert row["duration_seconds"] == 960


async def test_get_returns_the_route_as_saved(session: AsyncSession) -> None:
    repository = SQLAlchemyRouteRepository(session)
    # Real OSRM coordinates have up to 6 decimal places; nothing may be rounded away.
    route = Route(
        trip_id=uuid4(),
        path=(
            LatLng(lat=49.876812, lng=-97.143807),
            LatLng(lat=49.123456789012, lng=-97.987654321098),
            CAMPUS,
        ),
        distance_meters=6000,
        duration_seconds=900,
    )

    await repository.save(route)

    assert await repository.get(route.trip_id) == route


async def test_get_unknown_trip_returns_none(session: AsyncSession) -> None:
    assert await SQLAlchemyRouteRepository(session).get(uuid4()) is None

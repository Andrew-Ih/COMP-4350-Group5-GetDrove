"""Integration tests for the Routing repository (real PostgreSQL + PostGIS)."""

from collections.abc import AsyncIterator
from itertools import groupby
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import route_samples, routes
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import Corridor, LatLng
from routing.infrastructure.settings import get_settings

HOME = LatLng(lat=49.82, lng=-97.15)
CAMPUS = LatLng(lat=49.8075, lng=-97.1366)
CORRIDOR = Corridor(radius_meters=800)


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


async def saved_samples(session: AsyncSession, trip_id: UUID) -> list[RowMapping]:
    result = await session.execute(
        select(
            route_samples.c.seq,
            route_samples.c.offset_meters,
            route_samples.c.offset_seconds,
            func.ST_AsText(route_samples.c.point).label("wkt"),
        )
        .where(route_samples.c.trip_id == trip_id)
        .order_by(route_samples.c.seq)
    )
    return list(result.mappings())


async def save(session: AsyncSession, route: Route) -> None:
    await SQLAlchemyRouteRepository(session).save(route, sample_route(route))


def east_west(lat: float, trip_id: UUID | None = None) -> Route:
    """A 3 km route due east along a line of latitude, through Winnipeg."""
    west, east = LatLng(lat=lat, lng=-97.20), LatLng(lat=lat, lng=-97.158)
    return Route(
        trip_id=trip_id or uuid4(),
        path=(west, east),
        distance_meters=round(distance_meters(west, east)),
        duration_seconds=300,
    )


# ---------------------------------------------------------------- routes


async def test_save_stores_the_route_as_a_linestring(session: AsyncSession) -> None:
    route = Route(
        trip_id=uuid4(),
        path=(HOME, LatLng(lat=49.815, lng=-97.14), CAMPUS),
        distance_meters=6000,
        duration_seconds=900,
    )

    await save(session, route)

    row = await saved(session, route.trip_id)
    assert row["wkt"] == "LINESTRING(-97.15 49.82,-97.14 49.815,-97.1366 49.8075)"
    assert row["srid"] == 4326
    assert row["distance_meters"] == 6000
    assert row["duration_seconds"] == 900


async def test_save_again_replaces_the_route(session: AsyncSession) -> None:
    trip_id = uuid4()

    await save(
        session,
        Route(trip_id=trip_id, path=(HOME, CAMPUS), distance_meters=6000, duration_seconds=900),
    )
    await save(
        session,
        Route(trip_id=trip_id, path=(CAMPUS, HOME), distance_meters=6500, duration_seconds=960),
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

    await save(session, route)

    assert await repository.get(route.trip_id) == route


async def test_get_unknown_trip_returns_none(session: AsyncSession) -> None:
    assert await SQLAlchemyRouteRepository(session).get(uuid4()) is None


# ---------------------------------------------------------------- samples (#25)


async def test_save_stores_the_samples(session: AsyncSession) -> None:
    route = east_west(49.85)
    samples = sample_route(route)

    await save(session, route)

    rows = await saved_samples(session, route.trip_id)
    assert [row["seq"] for row in rows] == [sample.seq for sample in samples]
    assert [row["offset_meters"] for row in rows] == [s.offset_meters for s in samples]
    assert [row["offset_seconds"] for row in rows] == [s.offset_seconds for s in samples]
    assert rows[0]["wkt"] == "POINT(-97.2 49.85)"
    assert rows[-1]["wkt"] == "POINT(-97.158 49.85)"


async def test_save_again_replaces_the_samples(session: AsyncSession) -> None:
    trip_id = uuid4()
    await save(session, east_west(49.85, trip_id))
    shorter = Route(
        trip_id=trip_id, path=(HOME, CAMPUS), distance_meters=1500, duration_seconds=200
    )

    await save(session, shorter)

    rows = await saved_samples(session, trip_id)
    assert len(rows) == len(sample_route(shorter))
    assert rows[0]["wkt"] == "POINT(-97.15 49.82)"
    assert rows[-1]["offset_meters"] == 1500


async def test_deleting_a_route_deletes_its_samples(session: AsyncSession) -> None:
    route = east_west(49.85)
    await save(session, route)

    await session.execute(delete(routes).where(routes.c.trip_id == route.trip_id))

    assert await saved_samples(session, route.trip_id) == []


# ---------------------------------------------------------------- corridor (#25)


async def test_samples_in_corridor_finds_a_route_passing_near_the_rider(
    session: AsyncSession,
) -> None:
    route = east_west(49.85)
    await save(session, route)
    # About 300 m north of the route's midpoint.
    rider = LatLng(lat=49.8527, lng=-97.179)

    hits = await SQLAlchemyRouteRepository(session).samples_in_corridor(
        rider, [route.trip_id], CORRIDOR
    )

    assert hits
    assert {hit.trip_id for hit in hits} == {route.trip_id}
    distances = [hit.distance_meters for hit in hits]
    assert distances == sorted(distances)  # nearest first
    assert distances[0] == pytest.approx(300, abs=10)
    assert all(distance <= 800 for distance in distances)
    # The nearest sample is the one beside the rider, about halfway along the route.
    nearest = hits[0].sample
    assert nearest.point.lng == pytest.approx(-97.179, abs=0.001)
    assert nearest.offset_meters == pytest.approx(route.distance_meters / 2, abs=100)
    # About 800 m either side of the nearest point, at 100 m spacing.
    assert 13 <= len(hits) <= 17
    # What's left of the drive from each sample: a rider picked up there rides that far (#26).
    for corridor_hit in hits:
        expected = route.distance_meters - corridor_hit.sample.offset_meters
        assert corridor_hit.remaining_meters == expected


async def test_samples_in_corridor_leaves_out_routes_too_far_away(
    session: AsyncSession,
) -> None:
    near, far = east_west(49.85), east_west(49.87)  # the far one is about 2 km north
    await save(session, near)
    await save(session, far)

    hits = await SQLAlchemyRouteRepository(session).samples_in_corridor(
        LatLng(lat=49.8527, lng=-97.179), [near.trip_id, far.trip_id], CORRIDOR
    )

    assert {hit.trip_id for hit in hits} == {near.trip_id}


async def test_samples_in_corridor_only_searches_the_candidate_trips(
    session: AsyncSession,
) -> None:
    """Trips decides which trips are candidates (time, seats); others are never returned."""
    candidate, other = east_west(49.85), east_west(49.851)
    await save(session, candidate)
    await save(session, other)
    rider = LatLng(lat=49.8527, lng=-97.179)
    repository = SQLAlchemyRouteRepository(session)

    hits = await repository.samples_in_corridor(rider, [candidate.trip_id, uuid4()], CORRIDOR)

    assert {hit.trip_id for hit in hits} == {candidate.trip_id}
    assert await repository.samples_in_corridor(rider, [], CORRIDOR) == []


async def test_samples_in_corridor_groups_hits_by_trip(session: AsyncSession) -> None:
    first, second = east_west(49.85), east_west(49.855)
    await save(session, first)
    await save(session, second)

    hits = await SQLAlchemyRouteRepository(session).samples_in_corridor(
        LatLng(lat=49.8527, lng=-97.179), [first.trip_id, second.trip_id], CORRIDOR
    )

    # Each trip's hits are together: the trip changes only once in the list.
    runs = [trip_id for trip_id, _ in groupby(hit.trip_id for hit in hits)]
    assert sorted(runs) == sorted([first.trip_id, second.trip_id])
    # Nearest first within each trip.
    for trip_id in (first.trip_id, second.trip_id):
        distances = [hit.distance_meters for hit in hits if hit.trip_id == trip_id]
        assert distances == sorted(distances)


@pytest.mark.parametrize("radius,expected", [(250, 0), (350, 1)])
async def test_samples_in_corridor_respects_the_radius(
    session: AsyncSession, radius: int, expected: int
) -> None:
    route = east_west(49.85)
    await save(session, route)

    hits = await SQLAlchemyRouteRepository(session).samples_in_corridor(
        LatLng(lat=49.8527, lng=-97.179), [route.trip_id], Corridor(radius_meters=radius)
    )

    assert len({hit.trip_id for hit in hits}) == expected

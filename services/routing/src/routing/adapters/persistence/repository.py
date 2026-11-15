"""SQLAlchemy implementation of the Routing repository."""

import json
from collections.abc import Sequence
from uuid import UUID

from geoalchemy2 import Geography, Geometry, WKTElement
from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from routing.adapters.persistence.tables import SRID, route_samples, routes
from routing.domain.entities import Route
from routing.domain.values import Corridor, CorridorHit, LatLng, RouteSample

# ST_AsGeoJSON rounds to 9 decimal places by default; keep every digit that was stored.
MAX_DECIMAL_DIGITS = 15


def _linestring(route: Route) -> WKTElement:
    points = ", ".join(f"{point.lng} {point.lat}" for point in route.path)
    return WKTElement(f"LINESTRING({points})", srid=SRID)


def _point(point: LatLng) -> WKTElement:
    return WKTElement(f"POINT({point.lng} {point.lat})", srid=SRID)


class SQLAlchemyRouteRepository:
    """Store Route domain entities in PostgreSQL (PostGIS)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, route: Route, samples: Sequence[RouteSample]) -> None:
        values = {
            "path": _linestring(route),
            "distance_meters": route.distance_meters,
            "duration_seconds": route.duration_seconds,
        }
        statement = insert(routes).values(trip_id=route.trip_id, **values)
        # Computing a trip's route again replaces it (the contract allows retries).
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[routes.c.trip_id],
                set_={**values, "updated_at": func.now()},
            )
        )

        # The old route's samples go with it, in the same transaction.
        await self.session.execute(
            delete(route_samples).where(route_samples.c.trip_id == route.trip_id)
        )
        if samples:
            await self.session.execute(
                insert(route_samples),
                [
                    {
                        "trip_id": route.trip_id,
                        "seq": sample.seq,
                        "point": _point(sample.point),
                        "offset_meters": sample.offset_meters,
                        "offset_seconds": sample.offset_seconds,
                    }
                    for sample in samples
                ],
            )

    async def get(self, trip_id: UUID) -> Route | None:
        result = await self.session.execute(
            select(
                func.ST_AsGeoJSON(routes.c.path, MAX_DECIMAL_DIGITS).label("geojson"),
                routes.c.distance_meters,
                routes.c.duration_seconds,
            ).where(routes.c.trip_id == trip_id)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None

        # GeoJSON coordinates are [lng, lat] pairs.
        coordinates = json.loads(row["geojson"])["coordinates"]
        return Route(
            trip_id=trip_id,
            path=tuple(LatLng(lat=lat, lng=lng) for lng, lat in coordinates),
            distance_meters=row["distance_meters"],
            duration_seconds=row["duration_seconds"],
        )

    async def samples_in_corridor(
        self, rider: LatLng, trip_ids: Sequence[UUID], corridor: Corridor
    ) -> list[CorridorHit]:
        if not trip_ids:
            return []

        here = cast(_point(rider), Geography(srid=SRID))
        distance = func.ST_Distance(route_samples.c.point, here)
        # ST_X/ST_Y need a geometry; the cast keeps the same coordinates.
        point = cast(route_samples.c.point, Geometry(srid=SRID))
        start = cast(func.ST_StartPoint(routes.c.path), Geography(srid=SRID))
        end = cast(func.ST_EndPoint(routes.c.path), Geography(srid=SRID))
        result = await self.session.execute(
            select(
                route_samples.c.trip_id,
                route_samples.c.seq,
                func.ST_Y(point).label("lat"),
                func.ST_X(point).label("lng"),
                route_samples.c.offset_meters,
                route_samples.c.offset_seconds,
                distance.label("distance"),
                # Never negative: offsets are scaled to the route's distance (#25).
                (routes.c.distance_meters - route_samples.c.offset_meters).label("remaining"),
                func.least(
                    func.ST_Distance(route_samples.c.point, start),
                    func.ST_Distance(route_samples.c.point, end),
                ).label("from_ends"),
            )
            .join(routes, routes.c.trip_id == route_samples.c.trip_id)
            .where(
                route_samples.c.trip_id.in_(trip_ids),
                # Uses the GiST index on point; meters, because point is a geography.
                func.ST_DWithin(route_samples.c.point, here, corridor.radius_meters),
            )
            .order_by(route_samples.c.trip_id, distance, route_samples.c.seq)
        )

        return [
            CorridorHit(
                trip_id=row["trip_id"],
                sample=RouteSample(
                    seq=row["seq"],
                    point=LatLng(lat=row["lat"], lng=row["lng"]),
                    offset_meters=row["offset_meters"],
                    offset_seconds=row["offset_seconds"],
                ),
                distance_meters=round(row["distance"]),
                remaining_meters=row["remaining"],
                from_ends_meters=round(row["from_ends"]),
            )
            for row in result.mappings()
        ]

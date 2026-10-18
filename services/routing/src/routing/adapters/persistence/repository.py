"""SQLAlchemy implementation of the Routing repository."""

import json
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from routing.adapters.persistence.tables import SRID, routes
from routing.domain.entities import Route
from routing.domain.values import LatLng

# ST_AsGeoJSON rounds to 9 decimal places by default; keep every digit that was stored.
MAX_DECIMAL_DIGITS = 15


def _linestring(route: Route) -> WKTElement:
    points = ", ".join(f"{point.lng} {point.lat}" for point in route.path)
    return WKTElement(f"LINESTRING({points})", srid=SRID)


class SQLAlchemyRouteRepository:
    """Store Route domain entities in PostgreSQL (PostGIS)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, route: Route) -> None:
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

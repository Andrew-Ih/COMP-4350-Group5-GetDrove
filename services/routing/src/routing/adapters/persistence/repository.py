"""SQLAlchemy implementation of the Routing repository."""

from geoalchemy2 import WKTElement
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from routing.adapters.persistence.tables import SRID, routes
from routing.domain.entities import Route


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

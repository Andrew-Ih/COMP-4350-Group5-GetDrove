"""SQLAlchemy implementation of the Trips repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, RowMapping, and_, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, SearchWindow, TripStatus


def trip_from_row(row: RowMapping) -> Trip:
    return Trip(
        id=row[trips.c.id],
        driver_id=row["driver_id"],
        direction=Direction(row["direction"]),
        origin=Location(row["origin_label"], row["origin_lat"], row["origin_lng"]),
        destination=Location(
            row["destination_label"], row["destination_lat"], row["destination_lng"]
        ),
        departure_at=row["departure_at"],
        estimated_arrival_at=row["estimated_arrival_at"],
        duration_seconds=row["duration_seconds"],
        distance_meters=row["distance_meters"],
        seats_total=row["seats_total"],
        seats_available=row["seats_available"],
        status=TripStatus(row[trips.c.status]),
    )


def trip_list_filter(now: datetime, *, past: bool) -> ColumnElement[bool]:
    cutoff = func.coalesce(trips.c.estimated_arrival_at, trips.c.departure_at)
    status = trips.c.status
    is_past = or_(
        status == TripStatus.COMPLETED.value,
        and_(cutoff <= now, status != TripStatus.IN_PROGRESS.value),
    )
    return is_past if past else ~is_past


class SQLAlchemyTripRepository:
    """Store Trip domain entities in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, trip: Trip) -> None:
        await self.session.execute(
            insert(trips).values(
                id=trip.id,
                driver_id=trip.driver_id,
                direction=trip.direction.value,
                origin_label=trip.origin.label,
                origin_lat=trip.origin.lat,
                origin_lng=trip.origin.lng,
                destination_label=trip.destination.label,
                destination_lat=trip.destination.lat,
                destination_lng=trip.destination.lng,
                departure_at=trip.departure_at,
                estimated_arrival_at=trip.estimated_arrival_at,
                duration_seconds=trip.duration_seconds,
                distance_meters=trip.distance_meters,
                seats_total=trip.seats_total,
                seats_available=trip.seats_available,
                status=trip.status.value,
            )
        )

    async def get(self, trip_id: UUID) -> Trip | None:
        result = await self.session.execute(select(trips).where(trips.c.id == trip_id))
        row = result.mappings().one_or_none()
        return trip_from_row(row) if row is not None else None

    async def list_by_driver(self, driver_id: UUID, now: datetime, *, past: bool) -> list[Trip]:
        departure = trips.c.departure_at
        result = await self.session.execute(
            select(trips)
            .where(trips.c.driver_id == driver_id)
            .where(trip_list_filter(now, past=past))
            .order_by(departure.desc() if past else departure.asc(), trips.c.id)
        )
        return [trip_from_row(row) for row in result.mappings()]

    async def search(
        self, window: SearchWindow, departs_after: datetime, exclude_driver_id: UUID
    ) -> list[Trip]:
        time = trips.c.estimated_arrival_at if window.by_arrival else trips.c.departure_at
        result = await self.session.execute(
            select(trips)
            .where(
                trips.c.direction == window.direction.value,
                trips.c.status == TripStatus.SCHEDULED.value,
                trips.c.seats_available > 0,
                time.between(window.start, window.end),
                trips.c.departure_at > departs_after,
                trips.c.driver_id != exclude_driver_id,
            )
            .order_by(trips.c.departure_at, trips.c.id)
        )
        return [trip_from_row(row) for row in result.mappings()]

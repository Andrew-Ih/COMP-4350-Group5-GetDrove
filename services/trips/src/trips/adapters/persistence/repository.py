"""SQLAlchemy implementation of the Trips repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import seat_requests, trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, SearchWindow, TripStatus


def _trip(row: RowMapping) -> Trip:
    return Trip(
        id=row["id"],
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
        status=TripStatus(row["status"]),
    )


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

    async def get_for_update(self, trip_id: UUID) -> Trip | None:
        result = await self.session.execute(
            select(trips).where(trips.c.id == trip_id).with_for_update()
        )
        row = result.mappings().one_or_none()
        return _trip(row) if row is not None else None

    async def save_cancellation(self, trip: Trip) -> list[UUID]:
        await self.session.execute(
            update(trips).where(trips.c.id == trip.id).values(status=trip.status.value)
        )
        result = await self.session.execute(
            update(seat_requests)
            .where(
                seat_requests.c.trip_id == trip.id,
                seat_requests.c.status.in_(("pending", "accepted")),
            )
            .values(status="cancelled", decided_at=func.now(), pickup_order=None)
            .returning(seat_requests.c.rider_id)
        )
        return sorted(result.scalars())

    async def get_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]:
        result = await self.session.execute(
            select(trips)
            .where(trips.c.driver_id == driver_id)
            .where(trips.c.departure_at > now)
            .where(trips.c.status.in_((TripStatus.SCHEDULED.value, TripStatus.CANCELLED.value)))
            .order_by(trips.c.departure_at.asc())
        )
        return [_trip(row) for row in result.mappings()]

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
        return [_trip(row) for row in result.mappings()]

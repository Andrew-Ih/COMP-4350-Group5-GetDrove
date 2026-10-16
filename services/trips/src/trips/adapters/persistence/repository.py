"""SQLAlchemy implementation of the Trips repository."""

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip


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

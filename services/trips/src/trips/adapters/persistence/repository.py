"""SQLAlchemy implementation of the Trips repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, RowMapping, and_, func, insert, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import seat_requests, trip_series, trips
from trips.domain.entities import Trip, TripSeries
from trips.domain.values import Direction, Location, SearchWindow, TripStatus


def trip_from_row(row: RowMapping) -> Trip:
    return Trip(
        id=row[trips.c.id],
        driver_id=row[trips.c.driver_id],
        direction=Direction(row[trips.c.direction]),
        origin=Location(
            row[trips.c.origin_label], row[trips.c.origin_lat], row[trips.c.origin_lng]
        ),
        destination=Location(
            row[trips.c.destination_label],
            row[trips.c.destination_lat],
            row[trips.c.destination_lng],
        ),
        departure_at=row[trips.c.departure_at],
        estimated_arrival_at=row[trips.c.estimated_arrival_at],
        duration_seconds=row[trips.c.duration_seconds],
        distance_meters=row[trips.c.distance_meters],
        seats_total=row[trips.c.seats_total],
        seats_available=row[trips.c.seats_available],
        status=TripStatus(row[trips.c.status]),
        series_id=row[trips.c.series_id],
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

    async def lock_driver(self, driver_id: UUID) -> None:
        """Serialize recurring posts for this driver until the transaction ends."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:driver_id, 0))"),
            {"driver_id": f"trips.driver-trips:{driver_id}"},
        )

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
                series_id=trip.series_id,
            )
        )

    async def get(self, trip_id: UUID) -> Trip | None:
        result = await self.session.execute(select(trips).where(trips.c.id == trip_id))
        row = result.mappings().one_or_none()
        return trip_from_row(row) if row is not None else None

    async def get_for_update(self, trip_id: UUID) -> Trip | None:
        result = await self.session.execute(
            select(trips).where(trips.c.id == trip_id).with_for_update()
        )
        row = result.mappings().one_or_none()
        return trip_from_row(row) if row is not None else None

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

    async def get_cancellable_for_series(self, series_id: UUID, now: datetime) -> list[Trip]:
        result = await self.session.execute(
            select(trips)
            .where(
                trips.c.series_id == series_id,
                trips.c.status == TripStatus.SCHEDULED.value,
                trips.c.departure_at > now,
            )
            .order_by(trips.c.departure_at, trips.c.id)
            .with_for_update()
        )
        return [trip_from_row(row) for row in result.mappings()]

    async def list_by_driver(self, driver_id: UUID, now: datetime, *, past: bool) -> list[Trip]:
        departure = trips.c.departure_at
        result = await self.session.execute(
            select(trips)
            .where(trips.c.driver_id == driver_id)
            .where(trip_list_filter(now, past=past))
            .order_by(departure.desc() if past else departure.asc(), trips.c.id)
        )
        return [trip_from_row(row) for row in result.mappings()]

    async def get_active_or_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]:
        result = await self.session.execute(
            select(trips)
            .where(trips.c.driver_id == driver_id)
            .where(trips.c.estimated_arrival_at > now)
            .where(trips.c.status.in_((TripStatus.SCHEDULED.value, TripStatus.IN_PROGRESS.value)))
            .order_by(trips.c.departure_at.asc())
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


class SQLAlchemyTripSeriesRepository:
    """Store recurring trip series in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, series: TripSeries) -> None:
        await self.session.execute(
            insert(trip_series).values(
                id=series.id,
                driver_id=series.driver_id,
                direction=series.direction.value,
                place_label=series.place.label,
                place_lat=series.place.lat,
                place_lng=series.place.lng,
                departure_at=series.departure_at,
                seats_total=series.seats_total,
                weekdays=list(series.weekdays),
                end_date=series.end_date,
            )
        )

    async def get_by_id(self, series_id: UUID) -> TripSeries | None:
        result = await self.session.execute(
            select(trip_series).where(trip_series.c.id == series_id)
        )

        row = result.mappings().one_or_none()

        if row is None:
            return None

        return TripSeries(
            id=row["id"],
            driver_id=row["driver_id"],
            direction=Direction(row["direction"]),
            place=Location(
                row["place_label"],
                row["place_lat"],
                row["place_lng"],
            ),
            departure_at=row["departure_at"],
            seats_total=row["seats_total"],
            weekdays=tuple(row["weekdays"]),
            end_date=row["end_date"],
        )

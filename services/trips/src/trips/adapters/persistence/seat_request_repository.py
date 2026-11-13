"""SQLAlchemy persistence for seat requests."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import seat_requests, trips
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Location, Quote, TripStatus

ACTIVE = (RequestStatus.PENDING.value, RequestStatus.ACCEPTED.value)
OPEN_TRIP = (TripStatus.SCHEDULED.value, TripStatus.IN_PROGRESS.value)


def _request(row: RowMapping) -> SeatRequest:
    return SeatRequest(
        id=row["id"],
        trip_id=row["trip_id"],
        rider_id=row["rider_id"],
        pickup=Location(row["pickup_label"], row["pickup_lat"], row["pickup_lng"]),
        walk_seconds=row["walk_seconds"],
        rider_distance_meters=row["rider_distance_meters"],
        detour_seconds=row["detour_seconds"],
        cost=Quote(
            amount_cents=row["amount_cents"],
            currency=row["currency"],
            explanation=row["cost_explanation"],
        ),
        status=RequestStatus(row["status"]),
        auto_accepted=row["auto_accepted"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


class SQLAlchemySeatRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, request: SeatRequest) -> None:
        await self.session.execute(
            insert(seat_requests).values(
                id=request.id,
                trip_id=request.trip_id,
                rider_id=request.rider_id,
                status=request.status.value,
                pickup_label=request.pickup.label,
                pickup_lat=request.pickup.lat,
                pickup_lng=request.pickup.lng,
                walk_seconds=request.walk_seconds,
                rider_distance_meters=request.rider_distance_meters,
                detour_seconds=request.detour_seconds,
                amount_cents=request.cost.amount_cents,
                currency=request.cost.currency,
                cost_explanation=request.cost.explanation,
                auto_accepted=request.auto_accepted,
                created_at=request.created_at,
                decided_at=request.decided_at,
            )
        )

    async def get(self, request_id: UUID) -> SeatRequest | None:
        result = await self.session.execute(
            select(seat_requests).where(seat_requests.c.id == request_id)
        )
        row = result.mappings().first()
        return _request(row) if row is not None else None

    async def get_active_for_trip(self, trip_id: UUID, rider_id: UUID) -> SeatRequest | None:
        result = await self.session.execute(
            select(seat_requests)
            .where(seat_requests.c.trip_id == trip_id)
            .where(seat_requests.c.rider_id == rider_id)
            .where(seat_requests.c.status.in_(ACTIVE))
        )
        row = result.mappings().first()
        return _request(row) if row is not None else None

    async def has_overlapping_active_request(
        self, rider_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> bool:
        result = await self.session.execute(
            select(seat_requests.c.id)
            .join(trips, trips.c.id == seat_requests.c.trip_id)
            .where(seat_requests.c.rider_id == rider_id)
            .where(seat_requests.c.status.in_(ACTIVE))
            .where(trips.c.status.in_(OPEN_TRIP))
            .where(trips.c.departure_at < ends_at)
            .where(trips.c.estimated_arrival_at > starts_at)
            .limit(1)
        )
        return result.first() is not None

    async def list_accepted_pickups(self, trip_id: UUID) -> list[Location]:
        result = await self.session.execute(
            select(seat_requests)
            .where(seat_requests.c.trip_id == trip_id)
            .where(seat_requests.c.status == RequestStatus.ACCEPTED.value)
            .order_by(seat_requests.c.created_at.asc())
        )
        return [
            Location(row["pickup_label"], row["pickup_lat"], row["pickup_lng"])
            for row in result.mappings()
        ]

"""Dependencies for Trips API handlers."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common_web import current_request_id
from events.outbox import OutboxPublisher
from trips.adapters.events import OutboxTripEvents
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox
from trips.adapters.routing import HTTPRoutingService
from trips.application.post_trip import PostTrip
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location
from trips.application.upcoming_trips import ListUpcomingTrips


class PostTripCommand:
    """Runs trip posting within a database transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        routing: HTTPRoutingService,
    ) -> None:
        self.session_factory = session_factory
        self.routing = routing

    async def execute(
        self,
        *,
        driver_id: UUID,
        direction: Direction,
        place: Location,
        departure_at: datetime,
        seats_total: int,
    ) -> Trip:
        async with self.session_factory() as session:
            repository = SQLAlchemyTripRepository(session)
            events = OutboxTripEvents(
                OutboxPublisher(
                    session,
                    outbox,
                    producer="trips",
                    correlation_id=current_request_id(),
                )
            )

            use_case = PostTrip(repository, self.routing, events)

            async with session.begin():
                return await use_case.execute(
                    driver_id=driver_id,
                    direction=direction,
                    place=place,
                    departure_at=departure_at,
                    seats_total=seats_total,
                )


def get_post_trip(request: Request) -> PostTripCommand:
    return PostTripCommand(
        session_factory=request.app.state.session_factory,
        routing=HTTPRoutingService(request.app.state.routing_client),
    )


PostTripService = Annotated[PostTripCommand, Depends(get_post_trip)]



class UpcomingTripsCommand:
    """Runs the upcoming-trips query."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def execute(self, *, driver_id: UUID) -> list[Trip]:
        async with self.session_factory() as session:
            repository = SQLAlchemyTripRepository(session)
            use_case = ListUpcomingTrips(repository)
            return await use_case.execute(driver_id=driver_id)


def get_upcoming_trips(request: Request) -> UpcomingTripsCommand:
    return UpcomingTripsCommand(
        session_factory=request.app.state.session_factory,
    )


UpcomingTripsService = Annotated[
    UpcomingTripsCommand, Depends(get_upcoming_trips)
]


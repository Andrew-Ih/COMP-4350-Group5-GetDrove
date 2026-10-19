"""Dependencies for Trips API handlers."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common_web import current_request_id
from events.outbox import OutboxPublisher
from trips.adapters.events import OutboxTripEvents
from trips.adapters.payments import HTTPPricingService
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox
from trips.adapters.routing import HTTPRoutingService
from trips.application.post_trip import PostTrip
from trips.application.search_trips import SearchResult, SearchTrips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, Point


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


class SearchTripsQuery:
    """Runs a trip search, reading trips in its own database session."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        routing: HTTPRoutingService,
        pricing: HTTPPricingService,
    ) -> None:
        self.session_factory = session_factory
        self.routing = routing
        self.pricing = pricing

    async def execute(
        self, *, rider_id: UUID, rider: Point, direction: Direction, time: datetime
    ) -> list[SearchResult]:
        async with self.session_factory() as session:
            use_case = SearchTrips(SQLAlchemyTripRepository(session), self.routing, self.pricing)
            return await use_case.execute(rider_id, rider, direction, time)


def get_search_trips(request: Request) -> SearchTripsQuery:
    return SearchTripsQuery(
        session_factory=request.app.state.session_factory,
        routing=HTTPRoutingService(request.app.state.routing_client),
        pricing=HTTPPricingService(request.app.state.payments_client),
    )


SearchTripsService = Annotated[SearchTripsQuery, Depends(get_search_trips)]

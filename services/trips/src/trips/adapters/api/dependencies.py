"""Dependencies for Trips API handlers."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common_web import current_request_id
from events.outbox import OutboxPublisher
from trips.adapters.events import OutboxTripEvents
from trips.adapters.payments import HTTPPricingService
from trips.adapters.persistence.repository import (
    SQLAlchemyTripRepository,
    SQLAlchemyTripSeriesRepository,
)
from trips.adapters.persistence.tables import outbox
from trips.adapters.routing import HTTPRoutingService
from trips.application.post_recurring_trip import (
    PostRecurringTrip,
    PostRecurringTripResult,
)
from trips.application.post_trip import PostTrip
from trips.application.search_trips import SearchResult, SearchTrips
from trips.application.upcoming_trips import ListUpcomingTrips
from trips.domain.entities import Trip, TripSeries
from trips.domain.values import Direction, Location, Point


async def lock_driver_trips(
    session: AsyncSession,
    driver_id: UUID,
) -> None:
    """Serialize trip creation for a driver within a transaction."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:driver_id, 0))"),
        {"driver_id": str(driver_id)},
    )


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
                await lock_driver_trips(session, driver_id)

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


class PostRecurringTripCommand:
    """Post a recurring series within one database transaction."""

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
        series: TripSeries,
    ) -> PostRecurringTripResult:
        async with self.session_factory() as session:
            trip_repository = SQLAlchemyTripRepository(session)
            series_repository = SQLAlchemyTripSeriesRepository(session)

            events = OutboxTripEvents(
                OutboxPublisher(
                    session,
                    outbox,
                    producer="trips",
                    correlation_id=current_request_id(),
                )
            )

            use_case = PostRecurringTrip(
                trip_repository=trip_repository,
                series_repository=series_repository,
                routing=self.routing,
                events=events,
            )

            async with session.begin():
                await lock_driver_trips(session, series.driver_id)

                return await use_case.execute(series)


def get_post_recurring_trip(
    request: Request,
) -> PostRecurringTripCommand:
    return PostRecurringTripCommand(
        session_factory=request.app.state.session_factory,
        routing=HTTPRoutingService(request.app.state.routing_client),
    )


PostRecurringTripService = Annotated[
    PostRecurringTripCommand,
    Depends(get_post_recurring_trip),
]


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
        self,
        *,
        rider_id: UUID,
        rider: Point,
        direction: Direction,
        time: datetime,
    ) -> list[SearchResult]:
        async with self.session_factory() as session:
            use_case = SearchTrips(
                SQLAlchemyTripRepository(session),
                self.routing,
                self.pricing,
            )
            return await use_case.execute(
                rider_id,
                rider,
                direction,
                time,
            )


def get_search_trips(request: Request) -> SearchTripsQuery:
    return SearchTripsQuery(
        session_factory=request.app.state.session_factory,
        routing=HTTPRoutingService(request.app.state.routing_client),
        pricing=HTTPPricingService(request.app.state.payments_client),
    )


SearchTripsService = Annotated[SearchTripsQuery, Depends(get_search_trips)]


class UpcomingTripsCommand:
    """Runs the upcoming-trips query."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def execute(
        self,
        *,
        driver_id: UUID,
    ) -> list[Trip]:
        async with self.session_factory() as session:
            repository = SQLAlchemyTripRepository(session)
            use_case = ListUpcomingTrips(repository)
            return await use_case.execute(driver_id=driver_id)


def get_upcoming_trips(request: Request) -> UpcomingTripsCommand:
    return UpcomingTripsCommand(
        session_factory=request.app.state.session_factory,
    )


UpcomingTripsService = Annotated[
    UpcomingTripsCommand,
    Depends(get_upcoming_trips),
]

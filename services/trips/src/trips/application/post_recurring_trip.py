"""Application use case for posting recurring trips."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from trips.application.ports import (
    RoutingService,
    TripEvents,
    TripRepository,
    TripSeriesRepository,
)
from trips.domain.conflicts import has_trip_conflict
from trips.domain.entities import Trip, TripSeries
from trips.domain.errors import DepartureInPastError
from trips.domain.recurrence import expand_trip_series
from trips.domain.values import trip_ends


@dataclass
class PostRecurringTripResult:
    series: TripSeries
    created_trips: list[Trip]
    skipped_departures: list[datetime]


class PostRecurringTrip:
    def __init__(
        self,
        trip_repository: TripRepository,
        series_repository: TripSeriesRepository,
        routing: RoutingService,
        events: TripEvents,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.trip_repository = trip_repository
        self.series_repository = series_repository
        self.routing = routing
        self.events = events
        self.clock = clock or (lambda: datetime.now(UTC))

    async def prepare(self, series: TripSeries) -> list[Trip]:
        """Store a route under each candidate occurrence's ID before database work."""
        if series.departure_at <= self.clock():
            raise DepartureInPastError()

        origin, destination = trip_ends(series.direction, series.place)
        routing_slots = asyncio.Semaphore(8)

        async def prepare_occurrence(departure: datetime) -> Trip:
            trip_id = uuid4()
            async with routing_slots:
                route = await self.routing.compute_route(
                    trip_id, origin, destination, series.driver_id, series.direction
                )
            return Trip.create(
                driver_id=series.driver_id,
                direction=series.direction,
                place=series.place,
                departure_at=departure,
                duration_seconds=route.duration_seconds,
                distance_meters=route.distance_meters,
                seats_total=series.seats_total,
                series_id=series.id,
                trip_id=trip_id,
            )

        tasks = [
            asyncio.create_task(prepare_occurrence(departure))
            for departure in expand_trip_series(series)
        ]
        try:
            return await asyncio.gather(*tasks)
        except BaseException:
            # gather propagates the first failure without stopping sibling tasks.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def execute(self, series: TripSeries, candidates: list[Trip]) -> PostRecurringTripResult:
        """Check clashes and save prepared trips under the caller's transaction and lock."""
        now = self.clock()
        if series.departure_at <= now:
            raise DepartureInPastError()
        existing_trips = await self.trip_repository.get_active_or_upcoming_by_driver(
            series.driver_id, now
        )
        created_trips: list[Trip] = []
        skipped_departures: list[datetime] = []

        for trip in candidates:
            if has_trip_conflict(
                trip.departure_at,
                trip.estimated_arrival_at,
                existing_trips + created_trips,
            ):
                skipped_departures.append(trip.departure_at)
                continue

            created_trips.append(trip)

        # The command layer must wrap all writes
        # and event publishing in one transaction.
        await self.series_repository.add(series)

        for trip in created_trips:
            await self.trip_repository.add(trip)
            await self.events.trip_posted(trip.id)

        return PostRecurringTripResult(
            series=series,
            created_trips=created_trips,
            skipped_departures=skipped_departures,
        )

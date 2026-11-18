"""Application use case for cancelling a single trip."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import (
    SeriesCancellationRepository,
    TripCancellationEvents,
    TripCancellationRepository,
    TripSeriesLookup,
)
from trips.domain.entities import Trip
from trips.domain.errors import NotTripDriverError, SeriesNotFoundError, TripNotFoundError


class CancelTrip:
    def __init__(
        self,
        repository: TripCancellationRepository,
        events: TripCancellationEvents,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.events = events
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, *, trip_id: UUID, driver_id: UUID) -> Trip:
        trip = await self.repository.get_for_update(trip_id)
        if trip is None:
            raise TripNotFoundError()

        return await self.cancel_locked(trip, driver_id, self.clock())

    async def cancel_locked(self, trip: Trip, driver_id: UUID, cancelled_at: datetime) -> Trip:
        """Cancel an occurrence whose row is already locked by the caller."""
        is_late = trip.cancel(driver_id, cancelled_at)
        rider_ids = await self.repository.save_cancellation(trip)
        await self.events.trip_cancelled(trip, rider_ids)
        if is_late:
            await self.events.driver_late_cancellation(trip, cancelled_at)
        return trip


class CancelSeries:
    def __init__(
        self,
        repository: SeriesCancellationRepository,
        series_lookup: TripSeriesLookup,
        events: TripCancellationEvents,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.series_lookup = series_lookup
        self.clock = clock or (lambda: datetime.now(UTC))
        self.cancel_trip = CancelTrip(repository, events, self.clock)

    async def execute(self, *, series_id: UUID, driver_id: UUID) -> list[Trip]:
        series = await self.series_lookup.get_by_id(series_id)
        if series is None:
            raise SeriesNotFoundError()
        if series.driver_id != driver_id:
            raise NotTripDriverError("Only the series' driver can cancel it")

        candidates = await self.repository.get_cancellable_for_series(series_id, self.clock())
        # A departure can pass while we wait for a row lock.
        cancelled_at = self.clock()
        return [
            await self.cancel_trip.cancel_locked(trip, driver_id, cancelled_at)
            for trip in candidates
            if trip.can_cancel(cancelled_at)
        ]

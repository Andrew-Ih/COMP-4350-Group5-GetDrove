"""Series cancellation through the API against migrated PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.events import OutboxTripEvents
from trips.adapters.persistence.repository import (
    SQLAlchemyTripRepository,
    SQLAlchemyTripSeriesRepository,
)
from trips.adapters.persistence.seat_request_repository import SQLAlchemySeatRequestRepository
from trips.adapters.persistence.tables import outbox, seat_requests, trip_series, trips
from trips.domain.entities import WINNIPEG_TZ, Trip, TripSeries
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote, TripStatus
from trips.infrastructure.main import create_app

PLACE = Location("Pembina Highway", 49.82, -97.15)


@dataclass
class SeriesAPI:
    client: AsyncClient
    auth: TestAuth
    sessions: async_sessionmaker[AsyncSession]
    series: TripSeries
    now: datetime

    async def cancel(self) -> Response:
        return await self.client.post(
            f"/series/{self.series.id}/cancel", headers=self.auth.headers()
        )

    def occurrence(self, minutes: int, status: TripStatus = TripStatus.SCHEDULED) -> Trip:
        return replace(
            Trip.create(
                driver_id=self.series.driver_id,
                direction=self.series.direction,
                place=PLACE,
                departure_at=self.now + timedelta(minutes=minutes),
                duration_seconds=900,
                distance_meters=6000,
                seats_total=3,
                series_id=self.series.id,
            ),
            status=status,
        )


@pytest.fixture
async def api(trips_database: str) -> AsyncIterator[SeriesAPI]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(trips_database)
    sessions = async_sessionmaker(engine)
    app.state.session_factory = sessions
    now = datetime.now(UTC)
    local = now.astimezone(WINNIPEG_TZ)
    monday = local.date() - timedelta(days=local.weekday())
    series = TripSeries.create(
        driver_id=auth.user_id,
        direction=Direction.TO_CAMPUS,
        place=PLACE,
        departure_at=datetime.combine(monday, time(8), WINNIPEG_TZ),
        seats_total=3,
        weekdays=["mon", "wed", "fri"],
        end_date=monday + timedelta(weeks=2),
    )
    try:
        async with sessions.begin() as session:
            await SQLAlchemyTripSeriesRepository(session).add(series)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield SeriesAPI(client, auth, sessions, series, now)
    finally:
        try:
            async with sessions.begin() as session:
                trip_ids = select(trips.c.id).where(trips.c.driver_id == series.driver_id)
                await session.execute(
                    delete(outbox).where(
                        outbox.c.envelope["payload"]["driverId"].astext == str(series.driver_id)
                    )
                )
                await session.execute(
                    delete(seat_requests).where(seat_requests.c.trip_id.in_(trip_ids))
                )
                await session.execute(delete(trips).where(trips.c.driver_id == series.driver_id))
                await session.execute(delete(trip_series).where(trip_series.c.id == series.id))
        finally:
            await engine.dispose()


def seat_request(trip: Trip, status: RequestStatus, now: datetime) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=uuid4(),
        pickup=PLACE,
        walk_seconds=60,
        rider_distance_meters=5000,
        detour_seconds=120,
        cost=Quote(300, "CAD", "Saved fare"),
        now=now,
    )
    if status is RequestStatus.PENDING:
        return request
    return replace(
        request,
        status=status,
        decided_at=now,
        pickup_order=1 if status is RequestStatus.ACCEPTED else None,
    )


async def test_cancelling_one_occurrence_leaves_siblings_unchanged(api: SeriesAPI) -> None:
    earlier, selected, later = (api.occurrence(minutes) for minutes in (120, 240, 360))
    async with api.sessions.begin() as session:
        repository = SQLAlchemyTripRepository(session)
        for occurrence in (earlier, selected, later):
            await repository.add(occurrence)

    response = await api.client.post(f"/{selected.id}/cancel", headers=api.auth.headers())

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(selected.id)
    assert response.json()["status"] == "cancelled"
    assert response.json()["seriesId"] == str(api.series.id)
    async with api.sessions() as session:
        repository = SQLAlchemyTripRepository(session)
        assert await repository.get(selected.id) == replace(selected, status=TripStatus.CANCELLED)
        assert await repository.get(earlier.id) == earlier
        assert await repository.get(later.id) == later

    [event] = await cancellation_events(api)
    assert event["type"] == "TripCancelled"
    assert event["payload"]["tripId"] == str(selected.id)
    assert event["payload"]["seriesId"] == str(api.series.id)


async def test_series_cancellation_only_changes_eligible_occurrences(api: SeriesAPI) -> None:
    late, later = api.occurrence(30), api.occurrence(120)
    unchanged = [
        api.occurrence(-5),
        api.occurrence(-2, TripStatus.IN_PROGRESS),
        api.occurrence(-60, TripStatus.COMPLETED),
        api.occurrence(180, TripStatus.CANCELLED),
        replace(api.occurrence(240), series_id=None),
    ]
    pending = seat_request(late, RequestStatus.PENDING, api.now)
    accepted = seat_request(late, RequestStatus.ACCEPTED, api.now)
    declined = seat_request(late, RequestStatus.DECLINED, api.now)
    on_other_trip = seat_request(unchanged[-1], RequestStatus.PENDING, api.now)
    async with api.sessions.begin() as session:
        trip_repo = SQLAlchemyTripRepository(session)
        for trip in (later, *unchanged, late):
            await trip_repo.add(trip)
        request_repo = SQLAlchemySeatRequestRepository(session)
        for request in (pending, accepted, declined, on_other_trip):
            await request_repo.add(request)

    response = await api.cancel()
    assert response.status_code == 200, response.text
    assert [(trip["id"], trip["status"], trip["seriesId"]) for trip in response.json()] == [
        (str(trip.id), "cancelled", str(api.series.id)) for trip in (late, later)
    ]
    repeated = await api.cancel()
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == []

    async with api.sessions() as session:
        stored = await session.execute(
            select(trips.c.id, trips.c.status).where(trips.c.driver_id == api.series.driver_id)
        )
        assert dict(stored.all()) == {
            late.id: TripStatus.CANCELLED.value,
            later.id: TripStatus.CANCELLED.value,
            **{trip.id: trip.status.value for trip in unchanged},
        }
        requests = SQLAlchemySeatRequestRepository(session)
        for original in (pending, accepted):
            request = await requests.get(original.id)
            assert request is not None
            assert request.status is RequestStatus.CANCELLED
            assert request.pickup_order is None
        assert await requests.get(declined.id) == declined
        assert await requests.get(on_other_trip.id) == on_other_trip
        events = await cancellation_events(api)
        assert [event["type"] for event in events] == [
            "TripCancelled",
            "DriverLateCancellation",
            "TripCancelled",
        ]
        assert [event["payload"]["tripId"] for event in events] == [
            str(late.id),
            str(late.id),
            str(later.id),
        ]
        assert (
            events[0]["payload"]["seriesId"]
            == events[2]["payload"]["seriesId"]
            == str(api.series.id)
        )
        assert set(events[0]["payload"]["riderIds"]) == {
            str(pending.rider_id),
            str(accepted.rider_id),
        }
        assert events[2]["payload"]["riderIds"] == []


async def cancellation_events(api: SeriesAPI) -> list[dict[str, Any]]:
    async with api.sessions() as session:
        result = await session.scalars(
            select(outbox.c.envelope)
            .where(outbox.c.envelope["payload"]["driverId"].astext == str(api.series.driver_id))
            .order_by(outbox.c.id)
        )
        return list(result)


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("other_driver", 403, "not_trip_driver"),
        ("missing_series", 404, "series_not_found"),
        ("invalid_id", 422, "invalid_input"),
    ],
)
async def test_series_cancellation_rejects_invalid_requests(
    api: SeriesAPI, case: str, status: int, code: str
) -> None:
    trip = api.occurrence(120)
    async with api.sessions.begin() as session:
        await SQLAlchemyTripRepository(session).add(trip)
    series_id: UUID | str = api.series.id
    caller = api.auth.user_id
    if case == "other_driver":
        caller = uuid4()
    elif case == "missing_series":
        series_id = uuid4()
    else:
        series_id = "invalid"
    response = await api.client.post(
        f"/series/{series_id}/cancel", headers=api.auth.headers(user_id=caller)
    )

    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    async with api.sessions() as session:
        assert await SQLAlchemyTripRepository(session).get(trip.id) == trip
    assert await cancellation_events(api) == []


async def test_concurrent_series_cancellations_emit_each_event_once(
    api: SeriesAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = api.occurrence(120), api.occurrence(240)
    async with api.sessions.begin() as session:
        repository = SQLAlchemyTripRepository(session)
        await repository.add(first)
        await repository.add(second)

    first_writing = asyncio.Event()
    second_querying = asyncio.Event()
    get_candidates = SQLAlchemyTripRepository.get_cancellable_for_series
    save = SQLAlchemyTripRepository.save_cancellation

    async def record_selection(
        repo: SQLAlchemyTripRepository, series_id: UUID, now: datetime
    ) -> list[Trip]:
        if first_writing.is_set():
            second_querying.set()
        return await get_candidates(repo, series_id, now)

    async def hold_first_update(repo: SQLAlchemyTripRepository, trip: Trip) -> list[UUID]:
        first_writing.set()
        await second_querying.wait()
        return await save(repo, trip)

    monkeypatch.setattr(SQLAlchemyTripRepository, "get_cancellable_for_series", record_selection)
    monkeypatch.setattr(SQLAlchemyTripRepository, "save_cancellation", hold_first_update)

    async with asyncio.timeout(10), asyncio.TaskGroup() as tasks:
        winner = tasks.create_task(api.cancel())
        await first_writing.wait()
        loser = tasks.create_task(api.cancel())

    assert winner.result().status_code == loser.result().status_code == 200
    assert [trip["id"] for trip in winner.result().json()] == [str(first.id), str(second.id)]
    assert loser.result().json() == []
    assert [event["payload"]["tripId"] for event in await cancellation_events(api)] == [
        str(first.id),
        str(second.id),
    ]


async def test_series_cancellation_rolls_back_if_outbox_write_fails(
    api: SeriesAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = api.occurrence(120), api.occurrence(240)
    pending = seat_request(first, RequestStatus.PENDING, api.now)
    async with api.sessions.begin() as session:
        repository = SQLAlchemyTripRepository(session)
        await repository.add(first)
        await repository.add(second)
        await SQLAlchemySeatRequestRepository(session).add(pending)

    publish = OutboxTripEvents.trip_cancelled

    async def fail_second(events: OutboxTripEvents, trip: Trip, rider_ids: list[UUID]) -> None:
        if trip.id == second.id:
            raise RuntimeError("Outbox write failed")
        await publish(events, trip, rider_ids)

    monkeypatch.setattr(OutboxTripEvents, "trip_cancelled", fail_second)
    with pytest.raises(RuntimeError, match="Outbox write failed"):
        await api.cancel()

    async with api.sessions() as session:
        repository = SQLAlchemyTripRepository(session)
        assert await repository.get(first.id) == first
        assert await repository.get(second.id) == second
        assert await SQLAlchemySeatRequestRepository(session).get(pending.id) == pending
    assert await cancellation_events(api) == []

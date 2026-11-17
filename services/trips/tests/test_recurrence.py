"""Tests for recurring trip expansion."""

from datetime import UTC, date, datetime
from uuid import uuid4

from trips.domain.entities import WINNIPEG_TZ, TripSeries
from trips.domain.recurrence import expand_trip_series
from trips.domain.values import Direction, Location


def make_series(
    departure_at: datetime,
    weekdays: tuple[str, ...],
    end_date: date,
) -> TripSeries:
    return TripSeries.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=departure_at,
        seats_total=3,
        weekdays=weekdays,
        end_date=end_date,
    )


def test_expands_selected_weekdays() -> None:
    series = make_series(
        departure_at=datetime(2026, 11, 16, 8, tzinfo=WINNIPEG_TZ),
        weekdays=("mon", "wed", "fri"),
        end_date=date(2026, 11, 27),
    )

    departures = expand_trip_series(series)

    assert [departure.astimezone(WINNIPEG_TZ).date() for departure in departures] == [
        date(2026, 11, 16),
        date(2026, 11, 18),
        date(2026, 11, 20),
        date(2026, 11, 23),
        date(2026, 11, 25),
        date(2026, 11, 27),
    ]

    assert all(departure.astimezone(WINNIPEG_TZ).hour == 8 for departure in departures)


def test_uses_winnipeg_weekday_not_utc_weekday() -> None:
    series = make_series(
        departure_at=datetime.fromisoformat("2026-11-17T01:30:00+00:00"),
        weekdays=("mon",),
        end_date=date(2026, 11, 23),
    )

    departures = expand_trip_series(series)

    assert len(departures) == 2
    assert departures[0] == datetime(2026, 11, 17, 1, 30, tzinfo=UTC)
    assert departures[1].astimezone(WINNIPEG_TZ).date() == date(2026, 11, 23)


def test_preserves_local_time_across_dst() -> None:
    series = make_series(
        departure_at=datetime(2026, 3, 2, 8, tzinfo=WINNIPEG_TZ),
        weekdays=("mon",),
        end_date=date(2026, 3, 9),
    )

    departures = expand_trip_series(series)

    assert [
        (local.hour, local.minute)
        for local in (departure.astimezone(WINNIPEG_TZ) for departure in departures)
    ] == [(8, 0), (8, 0)]
    assert [departure.astimezone(UTC) for departure in departures] == [
        datetime(2026, 3, 2, 14, tzinfo=UTC),
        datetime(2026, 3, 9, 13, tzinfo=UTC),
    ]

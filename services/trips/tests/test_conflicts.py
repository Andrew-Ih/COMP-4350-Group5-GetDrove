"""Tests for trip conflict detection."""

from datetime import UTC, datetime
from uuid import uuid4

from trips.domain.conflicts import has_trip_conflict
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location


def make_trip(start_hour: int, start_minute: int = 0) -> Trip:
    return Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=datetime(2026, 11, 16, start_hour, start_minute, tzinfo=UTC),
        duration_seconds=1800,
        distance_meters=6000,
        seats_total=3,
    )


def test_detects_overlapping_trips() -> None:
    existing = make_trip(8)

    assert has_trip_conflict(
        datetime(2026, 11, 16, 8, 15, tzinfo=UTC),
        datetime(2026, 11, 16, 8, 45, tzinfo=UTC),
        [existing],
    )


def test_allows_non_overlapping_trips() -> None:
    existing = make_trip(8)

    assert not has_trip_conflict(
        datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
        datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
        [existing],
    )


def test_allows_adjacent_trips() -> None:
    existing = make_trip(8)

    assert not has_trip_conflict(
        datetime(2026, 11, 16, 8, 30, tzinfo=UTC),
        datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
        [existing],
    )


def test_detects_trip_contained_within_existing_trip() -> None:
    existing = make_trip(8)

    assert has_trip_conflict(
        datetime(2026, 11, 16, 8, 10, tzinfo=UTC),
        datetime(2026, 11, 16, 8, 20, tzinfo=UTC),
        [existing],
    )


def test_allows_trip_when_no_existing_trips() -> None:
    assert not has_trip_conflict(
        datetime(2026, 11, 16, 8, 0, tzinfo=UTC),
        datetime(2026, 11, 16, 8, 30, tzinfo=UTC),
        [],
    )

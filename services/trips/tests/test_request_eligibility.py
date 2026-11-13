"""Unit tests for seat-request eligibility rules."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from common_web.errors import DomainError
from trips.domain.entities import Trip
from trips.domain.request_eligibility import RequestEligibility, ensure_request_eligible
from trips.domain.values import Direction, Location, TripStatus


@pytest.fixture
def eligible() -> RequestEligibility:
    now = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location(label="Pembina Highway", lat=49.82, lng=-97.15),
        departure_at=now + timedelta(hours=1),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )

    return RequestEligibility(
        trip=trip,
        rider_id=uuid4(),
        now=now,
        already_requested=False,
        overlapping_request=False,
        has_card=True,
    )


def test_eligible_rider_is_allowed(eligible: RequestEligibility) -> None:
    ensure_request_eligible(eligible)


def test_missing_trip_returns_404(eligible: RequestEligibility) -> None:
    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, trip=None))

    assert error.value.code == "trip_not_found"
    assert error.value.status == 404


def test_driver_cannot_request_own_trip(eligible: RequestEligibility) -> None:
    assert eligible.trip is not None

    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, rider_id=eligible.trip.driver_id))

    assert error.value.code == "own_trip"
    assert error.value.status == 403


@pytest.mark.parametrize(
    ("changes", "expected_code"),
    [
        ({"already_requested": True}, "already_requested"),
        ({"overlapping_request": True}, "overlapping_request"),
        ({"has_card": False}, "card_required"),
    ],
)
def test_request_facts_reject_ineligible_riders(
    eligible: RequestEligibility,
    changes: dict[str, Any],
    expected_code: str,
) -> None:
    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, **changes))

    assert error.value.code == expected_code
    assert error.value.status == 409


def test_full_trip_is_rejected(eligible: RequestEligibility) -> None:
    assert eligible.trip is not None
    full_trip = replace(eligible.trip, seats_available=0)

    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, trip=full_trip))

    assert error.value.code == "trip_full"
    assert error.value.status == 409


@pytest.mark.parametrize(
    "status",
    [
        TripStatus.IN_PROGRESS,
        TripStatus.COMPLETED,
        TripStatus.CANCELLED,
    ],
)
def test_non_scheduled_trip_is_rejected(eligible: RequestEligibility, status: TripStatus) -> None:
    assert eligible.trip is not None
    trip = replace(eligible.trip, status=status)

    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, trip=trip))

    assert error.value.code == "trip_not_open"
    assert error.value.status == 409


@pytest.mark.parametrize("seconds_after_departure", [0, 1, 600])
def test_request_at_or_after_departure_is_rejected(
    eligible: RequestEligibility, seconds_after_departure: int
) -> None:
    assert eligible.trip is not None
    now = eligible.trip.departure_at + timedelta(seconds=seconds_after_departure)

    with pytest.raises(DomainError) as error:
        ensure_request_eligible(replace(eligible, now=now))

    assert error.value.code == "trip_not_open"
    assert error.value.status == 409


def test_last_available_seat_allows_a_request(eligible: RequestEligibility) -> None:
    assert eligible.trip is not None
    trip = replace(eligible.trip, seats_available=1)

    ensure_request_eligible(replace(eligible, trip=trip))

    assert trip.seats_available == 1


def test_current_time_requires_timezone(eligible: RequestEligibility) -> None:
    with pytest.raises(ValueError, match="Current time must include a timezone"):
        ensure_request_eligible(replace(eligible, now=datetime(2026, 11, 12, 18, 0)))

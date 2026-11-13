"""Tests for the seat-request domain model."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Location, Quote

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


def make(**changes: Any) -> SeatRequest:
    values: dict[str, Any] = {
        "trip_id": uuid4(),
        "rider_id": uuid4(),
        "pickup": Location("Pembina Highway pickup", 49.82, -97.15),
        "walk_seconds": 120,
        "rider_distance_meters": 9300,
        "detour_seconds": 180,
        "cost": Quote(420, "CAD", "9.3 km at $0.45/km"),
        "now": NOW,
    }
    values.update(changes)
    return SeatRequest.create(**values)


def test_new_request_starts_pending() -> None:
    request = make()

    assert request.status == RequestStatus.PENDING
    assert request.auto_accepted is False
    assert request.decided_at is None
    assert request.created_at == NOW


def test_request_preserves_pickup_and_quote() -> None:
    request = make()

    assert request.pickup.label == "Pembina Highway pickup"
    assert request.walk_seconds == 120
    assert request.rider_distance_meters == 9300
    assert request.detour_seconds == 180
    assert request.cost == Quote(420, "CAD", "9.3 km at $0.45/km")


def test_each_request_gets_a_new_id() -> None:
    assert make().id != make().id


@pytest.mark.parametrize(
    "change",
    [{"walk_seconds": -1}, {"rider_distance_meters": -1}, {"detour_seconds": -1}],
)
def test_negative_metrics_are_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        make(**change)


def test_unknown_detour_is_not_zero() -> None:
    assert make(detour_seconds=None).detour_seconds is None


@pytest.mark.parametrize(
    "pickup",
    [Location("   ", 49.8, -97.1), Location("Stop", 91, -97.1), Location("Stop", 49.8, 181)],
)
def test_invalid_pickup_is_rejected(pickup: Location) -> None:
    with pytest.raises(ValueError):
        make(pickup=pickup)


@pytest.mark.parametrize("cost", [Quote(-1, "CAD", "bad"), Quote(420, "USD", "bad")])
def test_invalid_cost_is_rejected(cost: Quote) -> None:
    with pytest.raises(ValueError):
        make(cost=cost)


def test_creation_time_requires_timezone() -> None:
    with pytest.raises(ValueError):
        make(now=datetime(2026, 11, 12, 18, 0))


def test_decision_time_requires_timezone() -> None:
    with pytest.raises(ValueError):
        replace(make(), decided_at=datetime(2026, 11, 12, 18, 5))


def test_decision_cannot_precede_creation() -> None:
    with pytest.raises(ValueError):
        replace(make(), decided_at=NOW - timedelta(seconds=1))


def test_decision_after_creation_is_allowed() -> None:
    decided = NOW + timedelta(minutes=1)

    assert replace(make(), decided_at=decided).decided_at == decided


def test_request_cannot_be_mutated_in_place() -> None:
    request = make()

    with pytest.raises(FrozenInstanceError):
        request.status = RequestStatus.ACCEPTED  # type: ignore[misc]

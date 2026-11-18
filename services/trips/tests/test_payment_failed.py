"""Definitive payment failures return an accepted seat once, preserving saved quotes."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from trips.application.payment_failed import HandlePaymentFailed
from trips.domain.request_errors import RequestNotFoundError
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Location, Quote

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def accepted_request() -> SeatRequest:
    return replace(
        SeatRequest.create(
            trip_id=uuid4(),
            rider_id=uuid4(),
            pickup=Location("Test stop", 49.8, -97.1),
            walk_seconds=120,
            rider_distance_meters=6000,
            detour_seconds=60,
            cost=Quote(270, "CAD", "Saved share"),
            now=NOW,
        ),
        status=RequestStatus.ACCEPTED,
        pickup_order=1,
    )


async def execute(repository, request):
    return await HandlePaymentFailed(repository).execute(
        request_id=request.id, trip_id=request.trip_id, rider_id=request.rider_id, now=NOW
    )


async def test_failure_returns_seat_and_preserves_quote() -> None:
    request = accepted_request()
    repository = AsyncMock()
    repository.get.return_value = request
    repository.save_decision.return_value = True
    assert await execute(repository, request)
    failed = repository.save_decision.await_args.args[0]
    assert failed.status is RequestStatus.PAYMENT_FAILED
    assert failed.pickup_order is None
    assert failed.cost == request.cost
    assert failed.rider_distance_meters == request.rider_distance_meters
    repository.release_seat.assert_awaited_once_with(request.trip_id)
    repository.renumber_accepted.assert_awaited_once_with(request.trip_id)


@pytest.mark.parametrize(
    "status", [status for status in RequestStatus if status is not RequestStatus.ACCEPTED]
)
async def test_nonaccepted_requests_do_not_return_another_seat(status) -> None:
    request = accepted_request()
    repository = AsyncMock()
    repository.get.return_value = replace(request, status=status, pickup_order=None)
    assert not await execute(repository, request)
    repository.save_decision.assert_not_awaited()
    repository.release_seat.assert_not_awaited()


async def test_cancellation_while_waiting_for_lock_is_not_double_counted() -> None:
    request = accepted_request()
    repository = AsyncMock()
    repository.get.side_effect = [request, request.cancel(NOW)]
    assert not await execute(repository, request)
    repository.release_seat.assert_not_awaited()


async def test_concurrent_transition_or_mismatched_identity_does_not_return_seat() -> None:
    request = accepted_request()
    repository = AsyncMock()
    repository.get.return_value = request
    repository.save_decision.return_value = False
    assert not await execute(repository, request)
    repository.release_seat.assert_not_awaited()
    with pytest.raises(ValueError, match="identity"):
        await HandlePaymentFailed(repository).execute(
            request_id=request.id, trip_id=uuid4(), rider_id=request.rider_id, now=NOW
        )
    repository.release_seat.assert_not_awaited()


async def test_unknown_request_is_not_acknowledged_as_success() -> None:
    request = accepted_request()
    repository = AsyncMock()
    repository.get.return_value = None
    with pytest.raises(RequestNotFoundError):
        await execute(repository, request)
    repository.release_seat.assert_not_awaited()

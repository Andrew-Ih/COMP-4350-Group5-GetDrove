from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from trips.application.rider_trips import ListRiderTrips


@pytest.mark.parametrize("past", [False, True])
async def test_lists_requests_for_rider_with_injected_time(past: bool) -> None:
    rider_id = uuid4()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    repository = AsyncMock()
    service = ListRiderTrips(repository, clock=lambda: now)

    result = await service.execute(rider_id, past=past)

    assert result is repository.list_by_rider.return_value
    repository.list_by_rider.assert_awaited_once_with(rider_id, now, past=past)

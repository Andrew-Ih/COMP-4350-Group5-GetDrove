
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from trips.application.upcoming_trips import ListUpcomingTrips


@pytest.mark.asyncio
async def test_execute_passes_driver_id_and_current_time_to_repository():
    driver_id = uuid4()
    now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)

    class FakeRepository:
        def __init__(self):
            self.received_driver_id = None
            self.received_now = None

        async def get_upcoming_by_driver(self, *, driver_id, now):
            self.received_driver_id = driver_id
            self.received_now = now
            return []

    repository = FakeRepository()
    service = ListUpcomingTrips(repository, clock=lambda: now)

    result = await service.execute(driver_id=driver_id)

    assert result == []
    assert repository.received_driver_id == driver_id
    assert repository.received_now == now

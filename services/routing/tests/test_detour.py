"""Unit tests for the detour use case (#36), with a fake repository and a fake matrix."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.detour import Detour, DetourCost
from routing.domain.entities import Route
from routing.domain.errors import RouteNotFoundError, RoutingEngineUnavailableError
from routing.domain.values import LatLng

TRIP = uuid4()
SECONDS_PER_STEP = 60


def at(north: int, east: int = 0) -> LatLng:
    """A point ``north`` steps north and ``east`` steps east of the origin."""
    return LatLng(lat=49.8 + north / 10_000, lng=-97.1 + east / 10_000)


def steps(point: LatLng) -> tuple[int, int]:
    return round((point.lat - 49.8) * 10_000), round((point.lng + 97.1) * 10_000)


START, END = at(0), at(10)


class FakeRepository:
    def __init__(self, trips: set[UUID] | None = None) -> None:
        self.trips = {TRIP} if trips is None else trips

    async def get(self, trip_id: UUID) -> Route | None:
        if trip_id not in self.trips:
            return None
        # A route with a bend in it: only its two ends matter.
        return Route(
            trip_id=trip_id,
            path=(START, at(5, 1), END),
            distance_meters=1000,
            duration_seconds=600,
        )


class FakeMatrix:
    """Drive time between two points: the steps between them, 60 s each."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.asked: list[list[LatLng]] = []

    async def durations(self, points: Sequence[LatLng]) -> list[list[float]]:
        self.asked.append(list(points))
        if self.error:
            raise self.error
        return [
            [
                float(
                    (abs(steps(a)[0] - steps(b)[0]) + abs(steps(a)[1] - steps(b)[1]))
                    * SECONDS_PER_STEP
                )
                for b in points
            ]
            for a in points
        ]


def detour_cost(matrix: FakeMatrix | None = None) -> tuple[DetourCost, FakeMatrix]:
    matrix = matrix or FakeMatrix()
    return DetourCost(FakeRepository(), matrix), matrix


async def test_the_first_rider_goes_first() -> None:
    use_case, _ = detour_cost()

    result = await use_case.execute(TRIP, [], at(4, 3))

    # Start to the pickup is 7 steps, the pickup to the end 9, the direct drive 10.
    assert result == Detour(added_seconds=6 * 60, position=0, total_seconds=16 * 60)


async def test_the_new_pickup_goes_where_it_costs_least() -> None:
    use_case, _ = detour_cost()

    result = await use_case.execute(TRIP, [at(3), at(6)], at(5, 2))

    # Before the first: 8 steps. Between them: 4. After the last: 6.
    assert result == Detour(added_seconds=4 * 60, position=1, total_seconds=14 * 60)


async def test_the_matrix_is_asked_for_the_points_in_the_order_the_insertion_expects() -> None:
    use_case, matrix = detour_cost()

    await use_case.execute(TRIP, [at(3), at(6)], at(5, 2))

    # The route's two ends, not the points between them.
    assert matrix.asked == [[START, at(3), at(6), at(5, 2), END]]


async def test_unknown_trip_is_not_found() -> None:
    use_case, matrix = detour_cost()

    with pytest.raises(RouteNotFoundError):
        await use_case.execute(uuid4(), [at(3)], at(4))
    assert matrix.asked == []


async def test_routing_engine_down_is_an_error() -> None:
    use_case, _ = detour_cost(FakeMatrix(error=RoutingEngineUnavailableError()))

    with pytest.raises(RoutingEngineUnavailableError):
        await use_case.execute(TRIP, [at(3)], at(4))

"""Unit tests for the detour use case (#36, #37), with a fake repository, matrix and plan
cache. Drive times are Manhattan steps of 60 s, so every number can be checked by hand."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.detour import Detour, DetourCost, plan_key
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
A1, A2 = at(3), at(6)


def cost(a: LatLng, b: LatLng) -> float:
    (north_a, east_a), (north_b, east_b) = steps(a), steps(b)
    return float((abs(north_a - north_b) + abs(east_a - east_b)) * SECONDS_PER_STEP)


class FakeRepository:
    def __init__(self, trips: set[UUID] | None = None) -> None:
        self.trips = {TRIP} if trips is None else trips

    async def route_ends(self, trip_id: UUID) -> tuple[LatLng, LatLng] | None:
        return (START, END) if trip_id in self.trips else None


class FakeMatrix:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.full: list[list[LatLng]] = []  # the points of each full matrix asked for
        self.around: list[tuple[LatLng, list[LatLng]]] = []  # a new pickup's row and column

    async def durations(self, points: Sequence[LatLng]) -> list[list[float]]:
        self.full.append(list(points))
        if self.error:
            raise self.error
        return [[cost(a, b) for b in points] for a in points]

    async def durations_around(
        self, point: LatLng, others: Sequence[LatLng]
    ) -> tuple[list[float], list[float]]:
        self.around.append((point, list(others)))
        if self.error:
            raise self.error
        return [cost(point, o) for o in others], [cost(o, point) for o in others]


class FakePlans:
    def __init__(self) -> None:
        self.plans: dict[tuple[UUID, str], list[list[float]]] = {}

    async def get(self, trip_id: UUID, key: str) -> list[list[float]] | None:
        return self.plans.get((trip_id, key))

    async def put(self, trip_id: UUID, key: str, matrix: list[list[float]]) -> None:
        self.plans[(trip_id, key)] = matrix

    async def forget(self, trip_id: UUID) -> None:
        self.plans = {k: v for k, v in self.plans.items() if k[0] != trip_id}


def detour_cost(
    matrix: FakeMatrix | None = None, plans: FakePlans | None = None
) -> tuple[DetourCost, FakeMatrix, FakePlans]:
    matrix, plans = matrix or FakeMatrix(), plans or FakePlans()
    return DetourCost(FakeRepository(), matrix, plans), matrix, plans


async def test_the_first_rider_goes_first() -> None:
    use_case, *_ = detour_cost()

    result = await use_case.execute(TRIP, [], at(4, 3))

    # Start to the pickup is 7 steps, the pickup to the end 9, the direct drive 10.
    assert result == Detour(added_seconds=6 * 60, position=0, total_seconds=16 * 60)


async def test_the_new_pickup_goes_where_it_costs_least() -> None:
    use_case, *_ = detour_cost()

    result = await use_case.execute(TRIP, [A1, A2], at(5, 2))

    # Before the first: 8 steps. Between them: 4. After the last: 6.
    assert result == Detour(added_seconds=4 * 60, position=1, total_seconds=14 * 60)


async def test_the_first_quote_asks_for_the_whole_matrix_in_the_insertions_order() -> None:
    use_case, matrix, _ = detour_cost()

    await use_case.execute(TRIP, [A1, A2], at(5, 2))

    assert matrix.full == [[START, A1, A2, at(5, 2), END]]
    assert matrix.around == []


async def test_a_second_quote_for_the_same_trip_only_asks_about_the_new_pickup() -> None:
    use_case, matrix, _ = detour_cost()
    await use_case.execute(TRIP, [A1, A2], at(5, 2))

    result = await use_case.execute(TRIP, [A1, A2], at(8, 1))

    assert len(matrix.full) == 1  # no second full matrix
    assert matrix.around == [(at(8, 1), [START, A1, A2, END])]
    # After the last pickup: 2 steps; the trip as it stands is 10.
    assert result == Detour(added_seconds=2 * 60, position=2, total_seconds=12 * 60)


async def test_a_cached_quote_gives_the_same_answer_as_a_fresh_one() -> None:
    use_case, *_ = detour_cost()
    fresh = await use_case.execute(TRIP, [A1, A2], at(5, 2))

    cached = await use_case.execute(TRIP, [A1, A2], at(5, 2))

    assert cached == fresh


async def test_a_changed_list_of_pickups_never_uses_the_old_plan() -> None:
    use_case, matrix, _ = detour_cost()
    await use_case.execute(TRIP, [A1, A2], at(5, 2))

    await use_case.execute(TRIP, [A1, A2, at(8)], at(9, 1))  # someone was accepted
    await use_case.execute(TRIP, [A1], at(5, 2))  # someone cancelled
    await use_case.execute(TRIP, [A2, A1], at(5, 2))  # a different order

    assert len(matrix.full) == 4
    assert matrix.around == []


async def test_forgetting_a_trip_drops_its_plans() -> None:
    use_case, matrix, plans = detour_cost()
    await use_case.execute(TRIP, [A1, A2], at(5, 2))

    await plans.forget(TRIP)
    await use_case.execute(TRIP, [A1, A2], at(8, 1))

    assert len(matrix.full) == 2


async def test_a_plan_of_the_wrong_size_is_ignored() -> None:
    use_case, matrix, plans = detour_cost()
    plans.plans[(TRIP, plan_key([START, A1, A2, END]))] = [[0.0]]

    result = await use_case.execute(TRIP, [A1, A2], at(5, 2))

    assert result == Detour(added_seconds=4 * 60, position=1, total_seconds=14 * 60)
    assert len(matrix.full) == 1


async def test_unknown_trip_is_not_found() -> None:
    use_case, matrix, plans = detour_cost()

    with pytest.raises(RouteNotFoundError):
        await use_case.execute(uuid4(), [A1], at(4))
    assert matrix.full == [] and matrix.around == [] and plans.plans == {}


async def test_routing_engine_down_is_an_error_and_saves_no_plan() -> None:
    use_case, _, plans = detour_cost(FakeMatrix(error=RoutingEngineUnavailableError()))

    with pytest.raises(RoutingEngineUnavailableError):
        await use_case.execute(TRIP, [A1], at(4))
    assert plans.plans == {}

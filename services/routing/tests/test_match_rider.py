"""Unit tests for the MatchRider application use case (#26)."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.match_rider import (
    DEFAULT_PICKUP_LABEL,
    SAMPLES_PER_TRIP,
    MatchRider,
)
from routing.domain.errors import RoutingEngineUnavailableError
from routing.domain.values import (
    Corridor,
    CorridorHit,
    LatLng,
    RiderMatch,
    RouteSample,
    Walk,
)

RIDER = LatLng(lat=49.85, lng=-97.15)
CORRIDOR = Corridor(radius_meters=800)
MAX_WALK = 600


def hit(trip_id: UUID, seq: int, distance: int = 300, remaining: int = 5000) -> CorridorHit:
    """A sample whose point is unique to its trip and seq, so fakes can key on it."""
    point = LatLng(lat=49.8 + seq / 10_000, lng=-97.1 - trip_id.int % 1000 / 10_000)
    return CorridorHit(
        trip_id=trip_id,
        sample=RouteSample(seq=seq, point=point, offset_meters=seq * 100, offset_seconds=seq * 9),
        distance_meters=distance,
        remaining_meters=remaining,
    )


class FakeRepository:
    def __init__(self, hits: list[CorridorHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[LatLng, list[UUID], Corridor]] = []

    async def samples_in_corridor(
        self, rider: LatLng, trip_ids: Sequence[UUID], corridor: Corridor
    ) -> list[CorridorHit]:
        self.calls.append((rider, list(trip_ids), corridor))
        return [h for h in self.hits if h.trip_id in trip_ids]


class FakeWalking:
    def __init__(self, walks: dict[LatLng, Walk | None], error: Exception | None = None) -> None:
        self.walks_by_point = walks
        self.error = error
        self.calls: list[tuple[LatLng, list[LatLng]]] = []

    async def walks(self, origin: LatLng, destinations: Sequence[LatLng]) -> list[Walk | None]:
        self.calls.append((origin, list(destinations)))
        if self.error:
            raise self.error
        return [self.walks_by_point.get(point) for point in destinations]


class FakeDriving:
    def __init__(self, names: dict[LatLng, str] | None = None) -> None:
        self.names = names or {}
        self.asked: list[LatLng] = []

    async def road_name(self, point: LatLng) -> str | None:
        self.asked.append(point)
        return self.names.get(point)


def walk(seconds: int) -> Walk:
    return Walk(seconds=seconds, meters=round(seconds * 1.39))


def match_rider(
    hits: list[CorridorHit],
    walks: dict[LatLng, Walk | None],
    names: dict[LatLng, str] | None = None,
) -> tuple[MatchRider, FakeRepository, FakeWalking, FakeDriving]:
    repository, walking, driving = FakeRepository(hits), FakeWalking(walks), FakeDriving(names)
    return (
        MatchRider(repository, walking, driving, CORRIDOR, MAX_WALK),
        repository,
        walking,
        driving,
    )


async def test_picks_the_sample_with_the_shortest_walk() -> None:
    trip = uuid4()
    near, nearer_on_foot = hit(trip, 10, distance=200), hit(trip, 11, distance=250, remaining=4100)
    use_case, repository, walking, driving = match_rider(
        [near, nearer_on_foot],
        {near.sample.point: walk(400), nearer_on_foot.sample.point: walk(180)},
        names={nearer_on_foot.sample.point: "Pembina Highway"},
    )

    matches = await use_case.execute(RIDER, [trip])

    assert matches == [
        RiderMatch(
            trip_id=trip,
            pickup=nearer_on_foot.sample.point,
            pickup_label="Pembina Highway",
            walk_seconds=180,
            rider_distance_meters=4100,
        )
    ]
    # One corridor query and one walking request, for every sample at once.
    assert repository.calls == [(RIDER, [trip], CORRIDOR)]
    assert walking.calls == [(RIDER, [near.sample.point, nearer_on_foot.sample.point])]
    assert driving.asked == [nearer_on_foot.sample.point]


async def test_a_trip_too_far_to_walk_to_does_not_match() -> None:
    """The rider across the river: inside the corridor, but a long walk round to a bridge."""
    reachable, across_river = uuid4(), uuid4()
    a, b = hit(reachable, 1), hit(across_river, 1, distance=150)
    use_case, *_ = match_rider([a, b], {a.sample.point: walk(500), b.sample.point: walk(2000)})

    matches = await use_case.execute(RIDER, [reachable, across_river])

    assert [m.trip_id for m in matches] == [reachable]


@pytest.mark.parametrize("seconds,matches", [(MAX_WALK, 1), (MAX_WALK + 1, 0)])
async def test_the_walking_limit_is_inclusive(seconds: int, matches: int) -> None:
    trip = uuid4()
    sample = hit(trip, 1)
    use_case, *_ = match_rider([sample], {sample.sample.point: walk(seconds)})

    assert len(await use_case.execute(RIDER, [trip])) == matches


async def test_samples_with_no_walking_route_are_skipped() -> None:
    trip = uuid4()
    unreachable, reachable = hit(trip, 1, distance=50), hit(trip, 2)
    use_case, *_ = match_rider(
        [unreachable, reachable],
        {unreachable.sample.point: None, reachable.sample.point: walk(300)},
    )

    [match] = await use_case.execute(RIDER, [trip])

    assert match.pickup == reachable.sample.point


async def test_no_trips_means_no_work() -> None:
    use_case, repository, walking, driving = match_rider([], {})

    assert await use_case.execute(RIDER, []) == []
    assert repository.calls == walking.calls == driving.asked == []


async def test_no_samples_in_the_corridor_skips_the_walking_check() -> None:
    use_case, repository, walking, _ = match_rider([], {})

    assert await use_case.execute(RIDER, [uuid4()]) == []
    assert len(repository.calls) == 1
    assert walking.calls == []


async def test_only_the_nearest_samples_of_each_trip_are_walked_to() -> None:
    trip = uuid4()
    hits = [hit(trip, seq, distance=seq) for seq in range(SAMPLES_PER_TRIP + 5)]
    use_case, _, walking, _ = match_rider(hits, {h.sample.point: walk(300) for h in hits})

    await use_case.execute(RIDER, [trip])

    [(_, destinations)] = walking.calls
    assert destinations == [h.sample.point for h in hits[:SAMPLES_PER_TRIP]]


async def test_matches_come_back_in_the_order_trips_asked_without_repeats() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()
    hits = [hit(third, 1), hit(first, 1), hit(second, 1)]
    use_case, *_ = match_rider(hits, {h.sample.point: walk(300) for h in hits})

    matches = await use_case.execute(RIDER, [second, third, second, first])

    assert [m.trip_id for m in matches] == [second, third, first]


async def test_a_road_with_no_name_gets_the_default_label() -> None:
    trip = uuid4()
    sample = hit(trip, 1)
    use_case, *_ = match_rider([sample], {sample.sample.point: walk(300)})

    [match] = await use_case.execute(RIDER, [trip])

    assert match.pickup_label == DEFAULT_PICKUP_LABEL


async def test_walking_engine_down_is_an_error() -> None:
    trip = uuid4()
    walking = FakeWalking({}, error=RoutingEngineUnavailableError())
    use_case = MatchRider(FakeRepository([hit(trip, 1)]), walking, FakeDriving(), CORRIDOR, 600)

    with pytest.raises(RoutingEngineUnavailableError):
        await use_case.execute(RIDER, [trip])

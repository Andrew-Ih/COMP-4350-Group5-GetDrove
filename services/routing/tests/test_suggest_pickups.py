"""Unit tests for choosing pickup points (#29): the shared rules and the SuggestPickups use
case, with a fake repository and fake routing engines."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.pickups import DEFAULT_PICKUP_LABEL, PRIVATE_END_METERS
from routing.application.suggest_pickups import SuggestPickups
from routing.domain.errors import RouteNotFoundError, RoutingEngineUnavailableError
from routing.domain.pickups import MIN_PICKUP_SPACING_METERS, is_excluded_road, pickup_id
from routing.domain.values import Corridor, CorridorHit, LatLng, PickupCandidate, RouteSample, Walk

RIDER = LatLng(lat=49.85, lng=-97.15)
CORRIDOR = Corridor(radius_meters=800)
MAX_WALK = 600
TRIP = uuid4()


def hit(seq: int, from_ends: int = 1000, trip_id: UUID = TRIP) -> CorridorHit:
    """Sample ``seq`` of a 5 km route, 100 m apart, so its offset is seq * 100."""
    point = LatLng(lat=49.8 + seq / 10_000, lng=-97.1)
    return CorridorHit(
        trip_id=trip_id,
        sample=RouteSample(seq=seq, point=point, offset_meters=seq * 100, offset_seconds=seq * 9),
        distance_meters=300,
        remaining_meters=5000 - seq * 100,
        from_ends_meters=from_ends,
    )


class FakeRepository:
    def __init__(self, hits: list[CorridorHit], trips: set[UUID] | None = None) -> None:
        self.hits = hits
        self.trips = {TRIP} if trips is None else trips

    async def has_route(self, trip_id: UUID) -> bool:
        return trip_id in self.trips

    async def samples_in_corridor(
        self, rider: LatLng, trip_ids: Sequence[UUID], corridor: Corridor
    ) -> list[CorridorHit]:
        return [h for h in self.hits if h.trip_id in trip_ids]


class FakeWalking:
    def __init__(self, seconds: dict[int, int | None], error: Exception | None = None) -> None:
        self.seconds = seconds  # by sample seq; missing means no walking route
        self.error = error
        self.calls = 0

    async def walks(self, origin: LatLng, destinations: Sequence[LatLng]) -> list[Walk | None]:
        self.calls += 1
        if self.error:
            raise self.error
        result: list[Walk | None] = []
        for point in destinations:
            s = self.seconds.get(round((point.lat - 49.8) * 10_000))
            result.append(None if s is None else Walk(seconds=s, meters=round(s * 1.39)))
        return result


class FakeDriving:
    def __init__(self, names: dict[int, str] | None = None) -> None:
        self.names = names or {}  # by sample seq
        self.asked: list[int] = []

    async def road_name(self, point: LatLng) -> str | None:
        seq = round((point.lat - 49.8) * 10_000)
        self.asked.append(seq)
        return self.names.get(seq)


def suggest(
    hits: list[CorridorHit],
    seconds: dict[int, int | None],
    names: dict[int, str] | None = None,
) -> tuple[SuggestPickups, FakeWalking, FakeDriving]:
    walking, driving = FakeWalking(seconds), FakeDriving(names)
    use_case = SuggestPickups(FakeRepository(hits), walking, driving, CORRIDOR, MAX_WALK)
    return use_case, walking, driving


# ---------------------------------------------------------------- domain rules


@pytest.mark.parametrize(
    "name",
    [
        "Abinojii Mikanah",  # Bishop Grandin Boulevard's name on the map since 2022
        "abinojii mikanah",
        "Bishop Grandin Boulevard",  # its old name, in older map data
        " Kenaston Boulevard ",
        "Perimeter Highway",
    ],
)
def test_fast_roads_are_excluded(name: str) -> None:
    assert is_excluded_road(name)


@pytest.mark.parametrize("name", ["Pembina Highway", "Dalhousie Drive", "Kenaston Street", ""])
def test_other_roads_are_not(name: str) -> None:
    assert not is_excluded_road(name)


def test_pickup_ids_name_the_sample() -> None:
    assert pickup_id(42) == "s42"


# ---------------------------------------------------------------- choosing pickup points


async def test_returns_points_shortest_walk_first_with_labels() -> None:
    hits = [hit(10), hit(13), hit(16)]
    use_case, walking, _ = suggest(
        hits, {10: 400, 13: 120, 16: 250}, names={13: "Pembina Highway", 16: "Point Road"}
    )

    pickups = await use_case.execute(TRIP, RIDER, limit=3)

    assert pickups == [
        PickupCandidate("s13", hits[1].sample.point, "Pembina Highway", 120, 3700),
        PickupCandidate("s16", hits[2].sample.point, "Point Road", 250, 3400),
        PickupCandidate("s10", hits[0].sample.point, DEFAULT_PICKUP_LABEL, 400, 4000),
    ]
    assert walking.calls == 1  # one walking request for all the samples


async def test_returns_at_most_the_limit() -> None:
    hits = [hit(seq) for seq in (10, 13, 16, 19)]
    use_case, _, driving = suggest(hits, {10: 100, 13: 200, 16: 300, 19: 400})

    pickups = await use_case.execute(TRIP, RIDER, limit=2)

    assert [p.id for p in pickups] == ["s10", "s13"]
    assert driving.asked == [10, 13]  # no road names asked for points not returned


async def test_points_on_excluded_roads_are_never_offered() -> None:
    hits = [hit(10), hit(13), hit(16)]
    use_case, *_ = suggest(
        hits,
        {10: 100, 13: 200, 16: 300},
        names={10: "Abinojii Mikanah", 13: "Kenaston Boulevard", 16: "Pembina Highway"},
    )

    pickups = await use_case.execute(TRIP, RIDER, limit=3)

    assert [(p.id, p.label) for p in pickups] == [("s16", "Pembina Highway")]


async def test_points_are_spread_out_along_the_route() -> None:
    """The next 100 m sample is the same spot for "choose a different point" (#136)."""
    hits = [hit(seq) for seq in (10, 11, 12, 13)]
    use_case, *_ = suggest(hits, {10: 100, 11: 110, 12: 120, 13: 130})

    pickups = await use_case.execute(TRIP, RIDER, limit=3)

    assert [p.id for p in pickups] == ["s10", "s12"]
    assert MIN_PICKUP_SPACING_METERS == 200


async def test_points_near_either_end_of_the_route_are_never_offered() -> None:
    hits = [hit(1, from_ends=100), hit(5, from_ends=PRIVATE_END_METERS - 1), hit(9)]
    use_case, *_ = suggest(hits, {1: 30, 5: 60, 9: 300})

    pickups = await use_case.execute(TRIP, RIDER, limit=3)

    assert [p.id for p in pickups] == ["s9"]


@pytest.mark.parametrize("seconds", [None, MAX_WALK + 1])
async def test_points_the_rider_cant_walk_to_are_never_offered(seconds: int | None) -> None:
    hits = [hit(10), hit(13)]
    use_case, *_ = suggest(hits, {10: seconds, 13: MAX_WALK})

    pickups = await use_case.execute(TRIP, RIDER, limit=3)

    assert [p.id for p in pickups] == ["s13"]


async def test_no_point_within_walking_distance_is_an_empty_list() -> None:
    use_case, walking, _ = suggest([], {})

    assert await use_case.execute(TRIP, RIDER, limit=3) == []
    assert walking.calls == 0


async def test_unknown_trip_is_not_found() -> None:
    use_case, walking, _ = suggest([hit(10)], {10: 100})

    with pytest.raises(RouteNotFoundError):
        await use_case.execute(uuid4(), RIDER, limit=3)
    assert walking.calls == 0


async def test_walking_engine_down_is_an_error() -> None:
    walking = FakeWalking({}, error=RoutingEngineUnavailableError())
    use_case = SuggestPickups(FakeRepository([hit(10)]), walking, FakeDriving(), CORRIDOR, 600)

    with pytest.raises(RoutingEngineUnavailableError):
        await use_case.execute(TRIP, RIDER, limit=3)

"""Unit tests for what of a route someone may see on the map (#135)."""

from uuid import uuid4

import pytest

from routing.domain.corridor import distance_meters
from routing.domain.entities import Route
from routing.domain.pickups import PRIVATE_END_METERS
from routing.domain.privacy import visible_path
from routing.domain.values import Direction, LatLng

# One thousandth of a degree of latitude is about 111.2 m anywhere on Earth.
METERS_PER_MILLIDEGREE_LAT = 111.195

HOME = LatLng(lat=49.8500, lng=-97.1500)
DRIVER = uuid4()


def north(meters: float, of: LatLng = HOME) -> LatLng:
    return LatLng(lat=of.lat + meters / METERS_PER_MILLIDEGREE_LAT / 1000, lng=of.lng)


def east(meters: float, of: LatLng = HOME) -> LatLng:
    # At Winnipeg's latitude a thousandth of a degree of longitude is about 71.7 m.
    return LatLng(lat=of.lat, lng=of.lng + meters / 71.71 / 1000)


def route(*path: LatLng, direction: Direction | None = Direction.TO_CAMPUS) -> Route:
    return Route(
        trip_id=uuid4(),
        path=path,
        distance_meters=2000,
        duration_seconds=240,
        driver_id=DRIVER if direction else None,
        direction=direction,
    )


# A 1 km drive due north from the driver's home, a point every 100 m.
STRAIGHT = tuple(north(m) for m in range(0, 1001, 100))


def nearest(point: LatLng, path: tuple[LatLng, ...]) -> float:
    return min(distance_meters(point, p) for p in path)


def test_the_driver_sees_the_whole_route() -> None:
    assert visible_path(route(*STRAIGHT), DRIVER) == STRAIGHT


def test_going_to_campus_the_start_is_cut_off_at_the_margin() -> None:
    seen = visible_path(route(*STRAIGHT), uuid4())

    assert distance_meters(HOME, seen[0]) == pytest.approx(PRIVATE_END_METERS, abs=0.5)
    assert nearest(HOME, seen) >= PRIVATE_END_METERS - 0.5
    # After the cut, the route's own points, unchanged, through to campus.
    assert seen[1:] == STRAIGHT[len(STRAIGHT) - len(seen) + 1 :]
    assert seen[-1] == STRAIGHT[-1]


def test_leaving_campus_the_end_is_cut_off_at_the_margin() -> None:
    leaving = tuple(reversed(STRAIGHT))  # from campus to the driver's home

    seen = visible_path(route(*leaving, direction=Direction.FROM_CAMPUS), uuid4())

    assert distance_meters(HOME, seen[-1]) == pytest.approx(PRIVATE_END_METERS, abs=0.5)
    assert nearest(HOME, seen) >= PRIVATE_END_METERS - 0.5
    assert seen[0] == leaving[0]  # the campus end stays


def test_the_cut_falls_inside_a_long_segment() -> None:
    """Straight roads have few points: the cut is on the segment, not at its far end."""
    far = north(2000)

    seen = visible_path(route(HOME, far), uuid4())

    assert distance_meters(HOME, seen[0]) == pytest.approx(PRIVATE_END_METERS, abs=0.5)
    assert seen[1] == far


def test_a_route_that_comes_back_past_home_is_cut_after_it_passes() -> None:
    """Leaving a cul-de-sac: out 250 m, back past the house, then away. Cutting at the first
    time it's 300 m out would still draw the loop beside the house."""
    loop = (
        HOME,
        east(250),
        north(150, east(250)),
        north(150),  # back beside the house, 150 m away
        north(400),
        north(800),
    )

    seen = visible_path(route(*loop), uuid4())

    assert nearest(HOME, seen) >= PRIVATE_END_METERS - 0.5
    assert seen[-2:] == loop[-2:]


def test_without_a_direction_both_ends_are_cut_off_for_everyone() -> None:
    """Routes stored before Sprint 2: no driver to show it to, and either end could be home."""
    old = route(*STRAIGHT, direction=None)

    seen = visible_path(old, DRIVER)

    assert nearest(STRAIGHT[0], seen) >= PRIVATE_END_METERS - 0.5
    assert nearest(STRAIGHT[-1], seen) >= PRIVATE_END_METERS - 0.5


def test_a_route_entirely_within_the_margin_shows_only_its_far_end() -> None:
    short = (HOME, north(100), north(200))

    seen = visible_path(route(*short), uuid4())

    assert seen == (short[-1], short[-1])

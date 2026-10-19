"""Unit tests for sampling a route evenly (#25)."""

from itertools import pairwise
from uuid import uuid4

import pytest

from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import Corridor, LatLng

# One thousandth of a degree of latitude is about 111.2 m anywhere on Earth.
METERS_PER_MILLIDEGREE_LAT = 111.195


def route(*path: LatLng, distance: int = 1000, duration: int = 120) -> Route:
    return Route(trip_id=uuid4(), path=path, distance_meters=distance, duration_seconds=duration)


def north_of(start: LatLng, meters: float) -> LatLng:
    return LatLng(lat=start.lat + meters / METERS_PER_MILLIDEGREE_LAT / 1000, lng=start.lng)


CAMPUS = LatLng(lat=49.8075, lng=-97.1366)


def test_distance_meters() -> None:
    assert distance_meters(CAMPUS, CAMPUS) == 0
    assert distance_meters(CAMPUS, north_of(CAMPUS, 1000)) == pytest.approx(1000, abs=0.5)
    # Osborne Village to campus, in a straight line.
    osborne = LatLng(lat=49.8768, lng=-97.1438)
    assert distance_meters(osborne, CAMPUS) == pytest.approx(7720, rel=0.01)


def test_samples_every_100_m_including_both_ends() -> None:
    end = north_of(CAMPUS, 1000)

    samples = sample_route(route(CAMPUS, end))

    assert [sample.seq for sample in samples] == list(range(11))
    assert samples[0].point == CAMPUS
    assert samples[-1].point == end
    for a, b in pairwise(samples):
        assert distance_meters(a.point, b.point) == pytest.approx(100, abs=0.5)


def test_offsets_are_scaled_to_the_routes_own_distance_and_duration() -> None:
    """OSRM's distance can differ slightly from the length of the drawn path. Offsets follow
    OSRM's numbers, so the end of the route is exactly its distance and duration."""
    samples = sample_route(route(CAMPUS, north_of(CAMPUS, 1000), distance=1100, duration=120))

    assert [sample.offset_meters for sample in samples] == list(range(0, 1101, 110))
    assert [sample.offset_seconds for sample in samples] == [round(i * 12) for i in range(11)]


def test_samples_follow_the_path_around_corners() -> None:
    """A path north then east: samples keep going along the road, not across the corner."""
    corner = north_of(CAMPUS, 250)
    # About 165 m east at Winnipeg's latitude.
    end = LatLng(lat=corner.lat, lng=corner.lng + 0.0023)
    path = (CAMPUS, corner, end)
    length = distance_meters(CAMPUS, corner) + distance_meters(corner, end)

    samples = sample_route(route(*path, distance=round(length)))

    assert length == pytest.approx(415, abs=1)
    assert len(samples) == 6  # 0, 100, 200, 300, 400 and the end
    assert samples[2].point.lng == CAMPUS.lng  # 200 m: still on the first stretch
    assert samples[3].point.lat == pytest.approx(corner.lat)  # 300 m: around the corner
    assert distance_meters(corner, samples[3].point) == pytest.approx(50, abs=0.5)


def test_many_short_segments() -> None:
    """Real routes have points a few meters apart: samples still land every 100 m."""
    path = tuple(north_of(CAMPUS, meters) for meters in range(0, 1001, 7))
    length = distance_meters(path[0], path[-1])

    samples = sample_route(route(*path, distance=round(length)))

    assert len(samples) == 11
    assert [sample.offset_meters for sample in samples[:-1]] == list(range(0, 1000, 100))


def test_route_shorter_than_the_spacing_has_just_its_ends() -> None:
    end = north_of(CAMPUS, 60)

    samples = sample_route(route(CAMPUS, end, distance=60, duration=10))

    assert [(s.seq, s.point, s.offset_meters) for s in samples] == [(0, CAMPUS, 0), (1, end, 60)]


@pytest.mark.parametrize("meters", [199.5, 200, 200.5])
def test_route_about_a_multiple_of_the_spacing_does_not_repeat_its_end(meters: float) -> None:
    """Float rounding makes "200 m" 199.9999 or 200.0002: never a sample right by the end."""
    samples = sample_route(route(CAMPUS, north_of(CAMPUS, meters)), spacing_meters=50)

    assert len(samples) == 5  # 0, 50, 100, 150 and the end
    assert distance_meters(samples[-2].point, samples[-1].point) == pytest.approx(50, abs=0.6)


def test_zero_length_route_has_one_sample() -> None:
    samples = sample_route(route(CAMPUS, CAMPUS, distance=0, duration=0))

    assert [(s.seq, s.point, s.offset_meters, s.offset_seconds) for s in samples] == [
        (0, CAMPUS, 0, 0)
    ]


@pytest.mark.parametrize("spacing", [0, -100])
def test_spacing_must_be_positive(spacing: int) -> None:
    with pytest.raises(ValueError, match="spacing"):
        sample_route(route(CAMPUS, north_of(CAMPUS, 1000)), spacing_meters=spacing)


def test_corridor_radius_must_be_positive() -> None:
    assert Corridor(radius_meters=800).radius_meters == 800
    for radius in (0, -1):
        with pytest.raises(ValueError, match="radius"):
            Corridor(radius_meters=radius)

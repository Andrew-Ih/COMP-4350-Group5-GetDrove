"""Points spaced evenly along a route, which the corridor around it is searched by (#25).

A stored route has uneven points: many on curves, few on long straight roads. Sampling it
every ``SAMPLE_SPACING_METERS`` gives every stretch of road the same weight when matching
riders, and each sample is a possible pickup point.
"""

import math
from itertools import pairwise

from routing.domain.entities import Route
from routing.domain.values import LatLng, RouteSample

SAMPLE_SPACING_METERS = 100

# A sample this close to the route's end would just repeat it: the end is always a sample.
END_TOLERANCE_METERS = 1.0

# Mean Earth radius (IUGG), for distances between nearby points.
EARTH_RADIUS_METERS = 6_371_008.8


def distance_meters(a: LatLng, b: LatLng) -> float:
    """Great-circle distance (haversine). Accurate to well under a meter at city scale."""
    lat_a, lat_b = math.radians(a.lat), math.radians(b.lat)
    d_lat = lat_b - lat_a
    d_lng = math.radians(b.lng - a.lng)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(h))


def _between(a: LatLng, b: LatLng, fraction: float) -> LatLng:
    # Straight-line interpolation is fine: route segments are at most a few hundred meters.
    return LatLng(lat=a.lat + (b.lat - a.lat) * fraction, lng=a.lng + (b.lng - a.lng) * fraction)


def sample_route(
    route: Route, spacing_meters: int = SAMPLE_SPACING_METERS
) -> tuple[RouteSample, ...]:
    """Points every ``spacing_meters`` along the route, from its start to its end (both
    included). Offsets are scaled to the route's own distance and duration, so the last
    sample is at exactly ``distance_meters`` and ``duration_seconds``."""
    if spacing_meters <= 0:
        raise ValueError("Sample spacing must be positive")

    segments = [distance_meters(a, b) for a, b in pairwise(route.path)]
    length = sum(segments)
    start, end = route.path[0], route.path[-1]
    if length == 0:
        return (RouteSample(seq=0, point=start, offset_meters=0, offset_seconds=0),)

    def sample(seq: int, point: LatLng, along: float) -> RouteSample:
        fraction = along / length
        return RouteSample(
            seq=seq,
            point=point,
            offset_meters=round(route.distance_meters * fraction),
            offset_seconds=round(route.duration_seconds * fraction),
        )

    samples = [sample(0, start, 0.0)]
    next_at = float(spacing_meters)
    last_at = length - END_TOLERANCE_METERS
    walked = 0.0
    for (a, b), segment in zip(pairwise(route.path), segments, strict=True):
        # Every sample that falls on this segment (a long straight road can hold several).
        while segment > 0 and next_at < walked + segment and next_at < last_at:
            samples.append(
                sample(len(samples), _between(a, b, (next_at - walked) / segment), next_at)
            )
            next_at += spacing_meters
        walked += segment

    samples.append(sample(len(samples), end, length))
    return tuple(samples)

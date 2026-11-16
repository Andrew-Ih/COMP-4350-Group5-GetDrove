"""What of a trip's route someone may see on the map (#135).

The driver sees all of it. Anyone else gets it with the driver's own end cut off, by the same
margin pickup points keep from the ends (PRIVATE_END_METERS, in a straight line), so the
driver's home is never shown. The cut is at the *last* point within that distance: a route
that leaves a cul-de-sac and comes back past the house is cut after it passes, not before.

Routes stored before Sprint 2 don't know their direction or driver, so both ends are cut for
everyone.
"""

from uuid import UUID

from routing.domain.corridor import distance_meters
from routing.domain.entities import Route
from routing.domain.pickups import PRIVATE_END_METERS
from routing.domain.values import Direction, LatLng

# Binary search steps for where a segment crosses the margin: 20 halvings of a segment a few
# hundred meters long is well under a millimeter.
_CROSSING_STEPS = 20


def visible_path(route: Route, viewer_id: UUID) -> tuple[LatLng, ...]:
    """The part of the route this person may see."""
    if route.driver_id is not None and viewer_id == route.driver_id:
        return route.path
    if route.direction == Direction.TO_CAMPUS:
        return _without_start(route.path)
    if route.direction == Direction.FROM_CAMPUS:
        return _without_end(route.path)
    # Unknown direction: either end could be the driver's.
    return _without_end(_without_start(route.path))


def _without_start(path: tuple[LatLng, ...]) -> tuple[LatLng, ...]:
    """The path from where it last leaves the margin around its first point."""
    start = path[0]
    inside = [
        i for i, point in enumerate(path) if distance_meters(start, point) < PRIVATE_END_METERS
    ]
    last = inside[-1]  # the start itself is always inside
    if last == len(path) - 1:
        # The whole route is within the margin: show only where it ends, as a line of no
        # length, so nothing near the driver's end is drawn.
        return (path[-1], path[-1])
    crossing = _crossing(start, path[last], path[last + 1])
    return (crossing, *path[last + 1 :])


def _without_end(path: tuple[LatLng, ...]) -> tuple[LatLng, ...]:
    return tuple(reversed(_without_start(tuple(reversed(path)))))


def _crossing(center: LatLng, inside: LatLng, outside: LatLng) -> LatLng:
    """The point on the segment from ``inside`` to ``outside`` that is PRIVATE_END_METERS
    from ``center`` (the segment starts within that distance and ends beyond it)."""
    low, high = 0.0, 1.0
    for _ in range(_CROSSING_STEPS):
        middle = (low + high) / 2
        if distance_meters(center, _between(inside, outside, middle)) < PRIVATE_END_METERS:
            low = middle
        else:
            high = middle
    return _between(inside, outside, high)


def _between(a: LatLng, b: LatLng, fraction: float) -> LatLng:
    return LatLng(lat=a.lat + (b.lat - a.lat) * fraction, lng=a.lng + (b.lng - a.lng) * fraction)

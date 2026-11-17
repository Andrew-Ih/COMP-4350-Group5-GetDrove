"""Where in a trip's pickup order a new rider fits (#38).

Pure arithmetic on a duration matrix. OSRM and the database stay out of it, so it is
tested with small hand-built matrices.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Insertion:
    """The cheapest place for a new pickup.

    ``position`` is how many accepted pickups come before it (0 = first), the same
    numbering Trips stores as ``detour_position`` (#310).
    """

    position: int
    added_seconds: float


def _added(durations: Sequence[Sequence[float]], before: int, new: int, after: int) -> float:
    return durations[before][new] + durations[new][after] - durations[before][after]


def cheapest_insertion(durations: Sequence[Sequence[float]], accepted_count: int) -> Insertion:
    """Try the new pickup at every position and keep the one that adds the least time.

    ``durations[i][j]`` is the drive time in seconds from point i to point j, over these
    points in order: the driver's start (0), the accepted pickups in their current order
    (1..n), the new pickup (n + 1) and the destination (n + 2). On a tie the earliest
    position wins. OSRM times can break the triangle inequality, so the result never goes
    below zero: a detour cannot make the trip shorter.
    """
    if accepted_count < 0:
        raise ValueError("The number of accepted pickups cannot be negative")
    size = accepted_count + 3
    if len(durations) != size or any(len(row) != size for row in durations):
        raise ValueError(f"Expected a {size}x{size} matrix for {accepted_count} accepted pickups")

    new, destination = accepted_count + 1, accepted_count + 2
    best = Insertion(0, _added(durations, 0, new, 1 if accepted_count else destination))
    for position in range(1, accepted_count + 1):
        after = position + 1 if position < accepted_count else destination
        added = _added(durations, position, new, after)
        if added < best.added_seconds:
            best = Insertion(position, added)
    return Insertion(best.position, max(best.added_seconds, 0))

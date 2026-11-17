"""A driver's auto-accept rules (#42): when a seat request is accepted without the driver.

A request is accepted automatically when the rules are on, its pickup adds at most
``max_detour_minutes``, the rider is rated at least ``min_rating`` (riders with no ratings yet
pass), and a seat is free (#43). ``auto_accept_allows`` makes that decision from plain facts,
so it can be tested on its own.
"""

from dataclasses import dataclass

from common_web.errors import InvalidField, InvalidInputError

DETOUR_MINUTES = range(0, 31)
MIN_RATING, MAX_RATING = 1.0, 5.0


@dataclass(frozen=True)
class AutoAcceptRules:
    """The defaults are what a driver who has never set any rules gets: off, 5 minutes, no
    minimum rating."""

    enabled: bool = False
    max_detour_minutes: int = 5
    min_rating: float | None = None  # None: any rating

    def __post_init__(self) -> None:
        errors: list[InvalidField] = []
        if self.max_detour_minutes not in DETOUR_MINUTES:
            errors.append(InvalidField(field="maxDetourMinutes", message="Use 0 to 30 minutes"))
        if self.min_rating is not None and not MIN_RATING <= self.min_rating <= MAX_RATING:
            errors.append(InvalidField(field="minRating", message="Use 1 to 5, or none"))
        if errors:
            raise InvalidInputError("Check your auto-accept rules.", errors=errors)

    def allows_detour(self, detour_seconds: int) -> bool:
        """Whether a pickup adding this much fits the rules (``detourSeconds <=
        maxDetourMinutes * 60``, as the contract says). A detour can't be negative (a seat
        request refuses one too), so that's a bug in the caller, not a "yes"."""
        if detour_seconds < 0:
            raise ValueError("Detour time cannot be negative")
        return detour_seconds <= self.max_detour_minutes * 60


def auto_accept_allows(
    rules: AutoAcceptRules,
    *,
    detour_seconds: int | None,
    rating_known: bool,
    rider_rating: float | None,
    seats_available: int,
) -> bool:
    """Whether a new request should be accepted without the driver (#43).

    Anything unknown means no, so the request waits for the driver: a detour Routing couldn't
    work out (``detour_seconds`` None), or a rating Accounts couldn't give when the rules have
    a minimum (``rating_known`` False). A rider with no ratings yet (``rider_rating`` None,
    but known) passes, as the contract says.
    """
    if not rules.enabled or seats_available <= 0:
        return False
    if detour_seconds is None or not rules.allows_detour(detour_seconds):
        return False
    if rules.min_rating is None:
        return True
    if not rating_known:
        return False
    return rider_rating is None or rider_rating >= rules.min_rating

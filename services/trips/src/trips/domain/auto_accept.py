"""A driver's auto-accept rules (#42): when a seat request is accepted without the driver.

A request is accepted automatically when the rules are on, its pickup adds at most
``max_detour_minutes``, the rider is rated at least ``min_rating`` (riders with no ratings yet
pass), and a seat is free. Evaluating requests against them is #43; this is just the rules.
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
        maxDetourMinutes * 60``, as the contract says)."""
        return detour_seconds <= self.max_detour_minutes * 60

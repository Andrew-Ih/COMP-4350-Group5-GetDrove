"""A student's reputation (#143): their ratings, completed trips and no-shows.

Everyone starts at zero. Ratings and no-shows are recorded from Sprint 3; until then the
numbers stay at zero and the rating is "none yet".
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Reputation:
    user_id: UUID
    # The sum and the count, not a stored average: adding a rating is then exact, with no
    # rounding drift.
    rating_sum: int = 0
    rating_count: int = 0
    trip_count: int = 0  # completed, as a driver or a rider
    no_show_count: int = 0

    @property
    def rating(self) -> float | None:
        """The average rating (1 to 5) to two decimals, or None until someone rates them."""
        if self.rating_count == 0:
            return None
        return round(self.rating_sum / self.rating_count, 2)

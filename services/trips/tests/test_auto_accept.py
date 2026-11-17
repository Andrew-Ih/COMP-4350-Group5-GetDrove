"""A driver's auto-accept rules (#42): the defaults, the limits, and saving and reading them."""

from uuid import UUID, uuid4

import pytest

from common_web.errors import InvalidInputError
from trips.application.auto_accept import GetAutoAcceptRules, SetAutoAcceptRules
from trips.domain.auto_accept import AutoAcceptRules, auto_accept_allows


class FakeAutoAcceptRules:
    def __init__(self) -> None:
        self.rows: dict[UUID, AutoAcceptRules] = {}

    async def get(self, driver_id: UUID) -> AutoAcceptRules | None:
        return self.rows.get(driver_id)

    async def save(self, driver_id: UUID, rules: AutoAcceptRules) -> None:
        self.rows[driver_id] = rules


def test_the_defaults_are_off_5_minutes_and_any_rating() -> None:
    assert AutoAcceptRules() == AutoAcceptRules(
        enabled=False, max_detour_minutes=5, min_rating=None
    )


@pytest.mark.parametrize("minutes", [0, 30])
def test_a_detour_of_0_to_30_minutes_is_allowed(minutes: int) -> None:
    assert AutoAcceptRules(max_detour_minutes=minutes).max_detour_minutes == minutes


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"max_detour_minutes": -1}, "maxDetourMinutes"),
        ({"max_detour_minutes": 31}, "maxDetourMinutes"),
        ({"min_rating": 0.9}, "minRating"),
        ({"min_rating": 5.1}, "minRating"),
    ],
)
def test_values_outside_the_limits_are_refused(change: dict[str, float], field: str) -> None:
    with pytest.raises(InvalidInputError) as refused:
        AutoAcceptRules(**change)  # type: ignore[arg-type]

    assert [error.field for error in refused.value.errors] == [field]


def test_every_invalid_field_is_named() -> None:
    with pytest.raises(InvalidInputError) as refused:
        AutoAcceptRules(max_detour_minutes=60, min_rating=9)

    assert {error.field for error in refused.value.errors} == {"maxDetourMinutes", "minRating"}


@pytest.mark.parametrize(
    ("detour_seconds", "allowed"), [(0, True), (299, True), (300, True), (301, False)]
)
def test_the_detour_limit_is_inclusive(detour_seconds: int, allowed: bool) -> None:
    # detourSeconds <= maxDetourMinutes * 60, as the contract says.
    assert AutoAcceptRules(max_detour_minutes=5).allows_detour(detour_seconds) is allowed


def test_a_negative_detour_is_refused_not_allowed() -> None:
    # Routing never returns one and a seat request can't hold one, so it's a bug upstream.
    with pytest.raises(ValueError, match="cannot be negative"):
        AutoAcceptRules(max_detour_minutes=5).allows_detour(-1)


async def test_a_driver_who_never_saved_rules_gets_the_defaults() -> None:
    assert await GetAutoAcceptRules(FakeAutoAcceptRules()).execute(uuid4()) == AutoAcceptRules()


async def test_saved_rules_are_read_back_and_can_be_replaced() -> None:
    repository, driver = FakeAutoAcceptRules(), uuid4()
    on = AutoAcceptRules(enabled=True, max_detour_minutes=10, min_rating=4.5)

    assert await SetAutoAcceptRules(repository).execute(driver, on) == on
    assert await GetAutoAcceptRules(repository).execute(driver) == on

    off = AutoAcceptRules(enabled=False, max_detour_minutes=10, min_rating=4.5)
    await SetAutoAcceptRules(repository).execute(driver, off)
    assert await GetAutoAcceptRules(repository).execute(driver) == off


# ---------------------------------------------------------------- the decision (#43)

ON = AutoAcceptRules(enabled=True, max_detour_minutes=5, min_rating=4.0)


@pytest.mark.parametrize(
    ("rules", "detour", "known", "rating", "seats", "accepted"),
    [
        (ON, 300, True, 4.5, 1, True),  # everything fits
        (ON, 300, True, None, 1, True),  # no ratings yet: passes
        (ON, 300, True, 4.0, 1, True),  # exactly the minimum
        (AutoAcceptRules(enabled=False), 0, True, 5.0, 3, False),  # off
        (ON, 301, True, 4.5, 1, False),  # detour one second too long
        (ON, None, True, 4.5, 1, False),  # detour unknown
        (ON, 300, True, 3.9, 1, False),  # rated too low
        (ON, 300, False, None, 1, False),  # Accounts couldn't say
        (ON, 300, True, 4.5, 0, False),  # no seat left
        # No minimum rating: the rating doesn't matter, even if unknown.
        (AutoAcceptRules(enabled=True, min_rating=None), 60, False, None, 1, True),
    ],
)
def test_auto_accept_allows(
    rules: AutoAcceptRules,
    detour: int | None,
    known: bool,
    rating: float | None,
    seats: int,
    accepted: bool,
) -> None:
    assert (
        auto_accept_allows(
            rules,
            detour_seconds=detour,
            rating_known=known,
            rider_rating=rating,
            seats_available=seats,
        )
        is accepted
    )

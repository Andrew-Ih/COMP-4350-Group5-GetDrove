"""SQLAlchemyTripMembers (#146) against a real PostgreSQL."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.trip_members import SQLAlchemyTripMembers
from notifications.domain.trip_members import TripRole

TRIP, DRIVER, RIDER, OTHER = uuid4(), uuid4(), uuid4(), uuid4()


async def test_driver_first_then_riders_and_adding_twice_is_harmless(
    session: AsyncSession,
) -> None:
    members = SQLAlchemyTripMembers(session)
    await members.add_rider(TRIP, RIDER)
    await members.add_driver(TRIP, DRIVER)
    await members.add_driver(TRIP, DRIVER)
    await members.add_rider(TRIP, RIDER)

    active = await members.active(TRIP)

    assert [(m.user_id, m.role) for m in active] == [
        (DRIVER, TripRole.DRIVER),
        (RIDER, TripRole.RIDER),
    ]


async def test_a_rider_who_leaves_is_inactive_and_can_come_back(session: AsyncSession) -> None:
    members = SQLAlchemyTripMembers(session)
    await members.add_driver(TRIP, DRIVER)
    await members.add_rider(TRIP, RIDER)

    await members.remove_rider(TRIP, RIDER)
    assert [m.user_id for m in await members.active(TRIP)] == [DRIVER]

    await members.add_rider(TRIP, RIDER)
    assert [m.user_id for m in await members.active(TRIP)] == [DRIVER, RIDER]


async def test_removing_a_rider_never_removes_the_driver(session: AsyncSession) -> None:
    members = SQLAlchemyTripMembers(session)
    await members.add_driver(TRIP, DRIVER)

    await members.remove_rider(TRIP, DRIVER)

    assert [m.user_id for m in await members.active(TRIP)] == [DRIVER]


async def test_a_cancelled_trip_has_nobody_on_it_and_others_are_untouched(
    session: AsyncSession,
) -> None:
    members = SQLAlchemyTripMembers(session)
    other_trip = uuid4()
    await members.add_driver(TRIP, DRIVER)
    await members.add_rider(TRIP, RIDER)
    await members.add_rider(other_trip, OTHER)

    await members.end_trip(TRIP)

    assert await members.active(TRIP) == []
    assert [m.user_id for m in await members.active(other_trip)] == [OTHER]

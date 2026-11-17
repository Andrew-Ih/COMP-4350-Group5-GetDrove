"""Public profiles and the internal user lookup (#143) over HTTP, against a real PostgreSQL."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import driver_profiles, reputation, users
from accounts.domain.user import User

# The log_in fixture (conftest.py): creates a verified student and logs them in.
LogIn = Callable[..., Awaitable[tuple[User, dict[str, str]]]]

CIVIC = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"}


async def make_driver(session: AsyncSession, user_id: UUID, status: str = "approved") -> None:
    await session.execute(
        insert(driver_profiles).values(
            user_id=user_id,
            status=status,
            vehicle_make="Honda",
            vehicle_model="Civic",
            vehicle_colour="Blue",
            vehicle_plate="ABC123",
        )
    )
    await session.commit()


async def test_a_profile_shows_only_public_fields(
    api: AsyncClient, log_in: LogIn, session: AsyncSession
) -> None:
    maya, _ = await log_in("maya")
    _, headers = await log_in("ada")
    await make_driver(session, maya.id)

    response = await api.get(f"/users/{maya.id}/profile", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": str(maya.id),
        "firstName": "Maya",
        "rating": None,
        "ratingCount": 0,
        "tripCount": 0,
        "isDriver": True,
        "vehicle": {"make": "Honda", "model": "Civic", "colour": "Blue"},  # no plate
    }


async def test_a_pending_driver_has_no_public_vehicle(
    api: AsyncClient, log_in: LogIn, session: AsyncSession
) -> None:
    tom, headers = await log_in("tom")
    await make_driver(session, tom.id, status="pending")

    body = (await api.get(f"/users/{tom.id}/profile", headers=headers)).json()

    assert (body["isDriver"], body["vehicle"]) == (False, None)


async def test_a_profile_shows_their_reputation(
    api: AsyncClient, log_in: LogIn, session: AsyncSession
) -> None:
    ada, headers = await log_in("ada")
    await session.execute(
        insert(reputation).values(user_id=ada.id, rating_sum=9, rating_count=2, trip_count=3)
    )
    await session.commit()

    body = (await api.get(f"/users/{ada.id}/profile", headers=headers)).json()

    assert (body["rating"], body["ratingCount"], body["tripCount"]) == (4.5, 2, 3)


async def test_an_unknown_user_is_404(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")

    response = await api.get(f"/users/{uuid4()}/profile", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


async def test_the_internal_lookup_returns_many_users_with_drivers_plates(
    api: AsyncClient, log_in: LogIn, session: AsyncSession
) -> None:
    maya, _ = await log_in("maya")
    noah, _ = await log_in("noah")
    await make_driver(session, maya.id)
    await session.execute(insert(reputation).values(user_id=noah.id, no_show_count=1))
    await session.commit()

    response = await api.get(
        "/internal/users", params={"ids": [str(maya.id), str(uuid4()), str(noah.id)]}
    )

    assert response.status_code == 200, response.text
    users = response.json()["users"]
    assert [user["id"] for user in users] == [str(maya.id), str(noah.id)]  # unknown left out
    assert users[0]["vehicle"] == CIVIC  # with the plate, for accepted riders
    assert users[1] == {
        "id": str(noah.id),
        "firstName": "Noah",
        "rating": None,
        "ratingCount": 0,
        "tripCount": 0,
        "noShowCount": 1,
        "vehicle": None,
    }
    assert "email" not in users[0]


async def test_deleting_a_user_deletes_their_reputation(
    log_in: LogIn, session: AsyncSession
) -> None:
    ada, _ = await log_in("ada")
    await session.execute(insert(reputation).values(user_id=ada.id))
    await session.commit()

    await session.execute(delete(users).where(users.c.id == ada.id))
    await session.commit()

    count = (await session.execute(select(func.count()).select_from(reputation))).scalar_one()
    assert count == 0


async def test_the_database_refuses_an_impossible_rating(
    log_in: LogIn, session: AsyncSession
) -> None:
    ada, _ = await log_in("ada")

    # One rating can add at most 5 to the sum.
    with pytest.raises(IntegrityError, match="ck_reputation_ratings_1_to_5"):
        await session.execute(
            insert(reputation).values(user_id=ada.id, rating_sum=6, rating_count=1)
        )

"""Applications to drive (#10) against a real PostgreSQL: the repository, and
GET /me/driver over HTTP, checked against contracts/openapi/accounts.json."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.driver_profile_repository import SqlDriverProfileRepository
from accounts.adapters.persistence.tables import users
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.email import Email
from accounts.domain.user import User

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)

# The log_in fixture (conftest.py): creates a verified student and logs them in.
LogIn = Callable[..., Awaitable[tuple[User, dict[str, str]]]]


async def student(session: AsyncSession, name: str = "ada") -> User:
    user = User.register(Email.parse(f"{name}@myumanitoba.ca"), "hash", name.title(), "Test")
    await SqlUserRepository(session).add(user)
    await session.commit()
    return user


# ---------------------------------------------------------------- the repository


async def test_a_profile_is_saved_and_read_back_whole(session: AsyncSession) -> None:
    ada, admin = await student(session), await student(session, "admin")
    profile = DriverProfile(ada.id, vehicle=Vehicle.create("Honda", "Civic", "Blue", "ABC123"))
    profile.submit_documents("licence/ada.pdf", "insurance/ada.png", NOW)
    profile.reject(admin.id, "Blurry licence.", NOW)
    drivers = SqlDriverProfileRepository(session)

    await drivers.save(profile)
    await session.commit()

    assert await drivers.get(ada.id) == profile


async def test_saving_again_updates_the_same_row(session: AsyncSession) -> None:
    ada = await student(session)
    drivers = SqlDriverProfileRepository(session)
    profile = DriverProfile(ada.id)
    await drivers.save(profile)
    profile.submit_documents("licence", "insurance", NOW)

    await drivers.save(profile)
    await session.commit()

    saved = await drivers.get(ada.id, for_update=True)
    assert saved is not None
    assert saved.status is DriverStatus.PENDING
    assert saved.vehicle is None


async def test_no_profile_is_none(session: AsyncSession) -> None:
    assert await SqlDriverProfileRepository(session).get(uuid4()) is None


async def test_deleting_the_user_deletes_their_profile(session: AsyncSession) -> None:
    ada = await student(session)
    drivers = SqlDriverProfileRepository(session)
    await drivers.save(DriverProfile(ada.id))
    await session.commit()

    await session.execute(delete(users).where(users.c.id == ada.id))
    await session.commit()

    assert await drivers.get(ada.id) is None


# ---------------------------------------------------------------- GET /me/driver


async def test_a_student_who_never_applied_sees_none(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")

    response = await api.get("/me/driver", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "none",
        "rejectionReason": None,
        "documents": {"licence": False, "insurance": False},
        "vehicle": None,
        "submittedAt": None,
        "reviewedAt": None,
    }


async def test_a_student_sees_their_application(
    api: AsyncClient,
    session: AsyncSession,
    log_in: LogIn,
) -> None:
    ada, headers = await log_in("ada")
    admin, _ = await log_in("admin", admin=True)
    profile = DriverProfile(ada.id, vehicle=Vehicle.create("Honda", "Civic", "Blue", "abc123"))
    profile.submit_documents("licence", "insurance", NOW)
    profile.reject(admin.id, "The insurance has expired.", NOW)
    await SqlDriverProfileRepository(session).save(profile)
    await session.commit()

    response = await api.get("/me/driver", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "rejected",
        "rejectionReason": "The insurance has expired.",
        "documents": {"licence": True, "insurance": True},
        "vehicle": {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"},
        "submittedAt": "2026-11-16T09:00:00Z",
        "reviewedAt": "2026-11-16T09:00:00Z",
    }


async def test_me_driver_needs_a_token(api: AsyncClient) -> None:
    response = await api.get("/me/driver")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"

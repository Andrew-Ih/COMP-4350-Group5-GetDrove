"""GET /internal/contacts (#146) against a real PostgreSQL: Notifications' way to find out
where to send an email, since events carry only user IDs."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.domain.email import Email
from accounts.domain.user import User


async def add_user(session: AsyncSession, email: str, first_name: str) -> User:
    user = User.register(Email.parse(email), "argon2-hash", first_name, "Student")
    await SqlUserRepository(session).add(user)
    await session.commit()
    return user


async def test_returns_names_and_emails_of_known_users(
    api: AsyncClient, session: AsyncSession
) -> None:
    ada = await add_user(session, "ada@myumanitoba.ca", "Ada")
    alan = await add_user(session, "alan@myumanitoba.ca", "Alan")
    await add_user(session, "grace@myumanitoba.ca", "Grace")  # not asked for

    response = await api.get("/internal/contacts", params={"ids": [str(alan.id), str(ada.id)]})

    assert response.status_code == 200
    assert response.json() == {
        "contacts": [
            {"id": str(alan.id), "firstName": "Alan", "email": "alan@myumanitoba.ca"},
            {"id": str(ada.id), "firstName": "Ada", "email": "ada@myumanitoba.ca"},
        ]
    }


async def test_unknown_ids_are_left_out(api: AsyncClient, session: AsyncSession) -> None:
    ada = await add_user(session, "ada@myumanitoba.ca", "Ada")

    response = await api.get("/internal/contacts", params={"ids": [str(uuid4()), str(ada.id)]})

    assert [contact["id"] for contact in response.json()["contacts"]] == [str(ada.id)]


async def test_nobody_known_is_an_empty_list(api: AsyncClient) -> None:
    response = await api.get("/internal/contacts", params={"ids": [str(uuid4())]})

    assert response.status_code == 200
    assert response.json() == {"contacts": []}

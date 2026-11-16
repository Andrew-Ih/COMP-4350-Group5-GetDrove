"""ListContacts (#146): names and emails for Notifications, by user ID."""

from uuid import uuid4

from accounts.application.contacts import ListContacts
from accounts.domain.email import Email
from accounts.domain.user import User
from accounts.testing import FakeUnitOfWork


def user(email: str, first_name: str) -> User:
    return User.register(Email.parse(email), "hash", first_name, "Student")


async def test_returns_the_asked_for_users_in_order() -> None:
    uow = FakeUnitOfWork()
    ada, alan = user("ada@myumanitoba.ca", "Ada"), user("alan@myumanitoba.ca", "Alan")
    await uow.users.add(ada)
    await uow.users.add(alan)
    await uow.users.add(user("grace@myumanitoba.ca", "Grace"))

    found = await ListContacts(uow)([alan.id, ada.id])

    assert [(u.first_name, u.email.value) for u in found] == [
        ("Alan", "alan@myumanitoba.ca"),
        ("Ada", "ada@myumanitoba.ca"),
    ]


async def test_unknown_and_repeated_ids_are_left_out() -> None:
    uow = FakeUnitOfWork()
    ada = user("ada@myumanitoba.ca", "Ada")
    await uow.users.add(ada)

    found = await ListContacts(uow)([ada.id, uuid4(), ada.id])

    assert [u.id for u in found] == [ada.id]


async def test_nothing_is_committed() -> None:
    uow = FakeUnitOfWork()

    await ListContacts(uow)([uuid4()])

    assert not uow.committed

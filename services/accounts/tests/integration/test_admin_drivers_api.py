"""Admins reviewing applications to drive (#127) over HTTP, against a real PostgreSQL:
the list, approving and rejecting (with their events in the outbox), and the make_admin
command."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import outbox, users
from accounts.domain.user import User
from accounts.infrastructure.make_admin import main as make_admin

# The log_in fixture (conftest.py): creates a verified student and logs them in.
LogIn = Callable[..., Awaitable[tuple[User, dict[str, str]]]]

FILES = {
    "licence": ("licence.pdf", b"%PDF-1.7", "application/pdf"),
    "insurance": ("insurance.png", b"\x89PNG\r\n\x1a\n", "image/png"),
}
CIVIC = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"}


async def apply(api: AsyncClient, headers: dict[str, str], *, vehicle: bool = True) -> None:
    """What the driver page does: save the vehicle, then upload both documents."""
    if vehicle:
        assert (await api.put("/me/driver/vehicle", json=CIVIC, headers=headers)).is_success
    assert (await api.put("/me/driver/documents", files=FILES, headers=headers)).is_success


async def outbox_events(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(select(outbox.c.envelope).order_by(outbox.c.id))
    return [row.envelope for row in rows]


def assert_problem(response: Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code


@pytest.fixture
async def admin(log_in: LogIn) -> dict[str, str]:
    _, headers = await log_in("admin", admin=True)
    return headers


# ---------------------------------------------------------------- the list


async def test_pending_applications_are_listed_oldest_first(
    api: AsyncClient, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    bob, bob_headers = await log_in("bob")
    _, cleo_headers = await log_in("cleo")
    await apply(api, ada_headers)
    await apply(api, bob_headers, vehicle=False)
    await api.put("/me/driver/vehicle", json=CIVIC, headers=cleo_headers)  # never applied

    response = await api.get("/admin/drivers", headers=admin)

    assert response.status_code == 200
    body = response.json()
    assert [driver["userId"] for driver in body] == [str(ada.id), str(bob.id)]
    first = body[0]
    assert first["firstName"] == "Ada"
    assert first["email"] == "ada@myumanitoba.ca"
    assert first["status"] == "pending"
    assert first["vehicle"]["plate"] == "ABC123"
    assert first["documents"] == {"licence": True, "insurance": True}
    assert body[1]["vehicle"] is None


async def test_the_list_filters_by_status(
    api: AsyncClient, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    assert (await api.get("/admin/drivers?status=approved", headers=admin)).json() == []
    await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)
    approved = (await api.get("/admin/drivers?status=approved", headers=admin)).json()

    assert [driver["userId"] for driver in approved] == [str(ada.id)]
    assert (await api.get("/admin/drivers", headers=admin)).json() == []


# ---------------------------------------------------------------- approving


async def test_approving_a_driver(
    api: AsyncClient, session: AsyncSession, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    response = await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["reviewedAt"] is not None
    # The driver sees it straight away...
    mine = (await api.get("/me/driver", headers=ada_headers)).json()
    assert mine["status"] == "approved"
    # ...and Trips and Notifications will hear about it, through the outbox.
    [event] = await outbox_events(session)
    assert event["type"] == "DriverApproved"
    assert event["producer"] == "accounts"
    assert event["payload"] == {"userId": str(ada.id)}


async def test_approving_without_a_vehicle_is_409(
    api: AsyncClient, session: AsyncSession, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers, vehicle=False)

    response = await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)

    assert_problem(response, 409, "vehicle_missing")
    assert await outbox_events(session) == []


async def test_deciding_twice_is_409(
    api: AsyncClient, session: AsyncSession, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)
    await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)

    again = await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)
    reject = await api.post(
        f"/admin/drivers/{ada.id}/reject", json={"reason": "Oops."}, headers=admin
    )

    assert_problem(again, 409, "driver_not_pending")
    assert_problem(reject, 409, "driver_not_pending")
    assert len(await outbox_events(session)) == 1


async def test_a_student_who_never_applied_is_404(
    api: AsyncClient, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await api.put("/me/driver/vehicle", json=CIVIC, headers=ada_headers)
    nobody = "0c8d6a1e-7b44-4f0e-8f61-6a2a9d3c5e77"

    for user_id in (ada.id, nobody):
        response = await api.post(f"/admin/drivers/{user_id}/approve", headers=admin)
        assert_problem(response, 404, "driver_not_found")


# ---------------------------------------------------------------- rejecting


async def test_rejecting_a_driver_with_a_reason(
    api: AsyncClient, session: AsyncSession, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    response = await api.post(
        f"/admin/drivers/{ada.id}/reject",
        json={"reason": "The insurance has expired."},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    mine = (await api.get("/me/driver", headers=ada_headers)).json()
    assert mine["rejectionReason"] == "The insurance has expired."
    [event] = await outbox_events(session)
    assert event["type"] == "DriverRejected"
    assert event["payload"] == {"userId": str(ada.id), "reason": "The insurance has expired."}


async def test_a_rejected_driver_can_upload_again_and_be_approved(
    api: AsyncClient, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)
    await api.post(f"/admin/drivers/{ada.id}/reject", json={"reason": "Blurry."}, headers=admin)

    await api.put("/me/driver/documents", files=FILES, headers=ada_headers)
    response = await api.post(f"/admin/drivers/{ada.id}/approve", headers=admin)

    assert response.json()["status"] == "approved"
    assert response.json()["rejectionReason"] is None


async def test_a_blank_reason_is_422(
    api: AsyncClient, log_in: LogIn, admin: dict[str, str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    response = await api.post(
        f"/admin/drivers/{ada.id}/reject", json={"reason": "   "}, headers=admin
    )

    assert_problem(response, 422, "invalid_input")


# ---------------------------------------------------------------- students can't


async def test_a_student_cant_approve_themselves(api: AsyncClient, log_in: LogIn) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    response = await api.post(f"/admin/drivers/{ada.id}/approve", headers=ada_headers)

    assert_problem(response, 403, "forbidden")
    assert (await api.get("/me/driver", headers=ada_headers)).json()["status"] == "pending"


# ---------------------------------------------------------------- make_admin


async def test_make_admin_gives_the_role_at_the_next_login(
    api: AsyncClient, session: AsyncSession, log_in: LogIn, capsys: pytest.CaptureFixture[str]
) -> None:
    ada, ada_headers = await log_in("ada")
    await apply(api, ada_headers)

    # The command calls asyncio.run, so it runs in its own thread, away from the test's loop.
    code = await asyncio.to_thread(make_admin, ["ada@myumanitoba.ca"])

    assert code == 0
    assert "is an admin" in capsys.readouterr().out
    is_admin = await session.scalar(select(users.c.is_admin).where(users.c.id == ada.id))
    assert is_admin is True
    login = await api.post(
        "/auth/login", json={"email": "ada@myumanitoba.ca", "password": "correct horse battery"}
    )
    new_headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert (await api.get("/admin/drivers", headers=new_headers)).status_code == 200


async def test_make_admin_for_an_unknown_email_fails(
    session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    code = await asyncio.to_thread(make_admin, ["nobody@myumanitoba.ca"])

    assert code == 1
    assert "Nobody was made an admin" in capsys.readouterr().err


def test_make_admin_needs_exactly_one_email(capsys: pytest.CaptureFixture[str]) -> None:
    assert make_admin([]) == 2
    assert "Usage" in capsys.readouterr().err

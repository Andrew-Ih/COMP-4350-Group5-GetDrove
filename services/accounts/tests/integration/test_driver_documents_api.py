"""Driver documents over HTTP (#9), against a real PostgreSQL and a temporary folder,
checked against contracts/openapi/accounts.json."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.driver_profile_repository import SqlDriverProfileRepository
from accounts.domain.documents import MAX_DOCUMENT_BYTES
from accounts.domain.driver import Vehicle
from accounts.domain.user import User

# The log_in fixture (conftest.py): creates a verified student and logs them in.
LogIn = Callable[..., Awaitable[tuple[User, dict[str, str]]]]

PDF = b"%PDF-1.7 licence"
PNG = b"\x89PNG\r\n\x1a\n insurance"
FILES = {
    "licence": ("licence.pdf", PDF, "application/pdf"),
    "insurance": ("insurance.png", PNG, "image/png"),
}


def assert_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


async def test_uploading_both_documents_makes_the_application_pending(
    api: AsyncClient, log_in: LogIn
) -> None:
    _, headers = await log_in("ada")

    response = await api.put("/me/driver/documents", files=FILES, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["documents"] == {"licence": True, "insurance": True}
    assert body["submittedAt"] is not None
    assert (await api.get("/me/driver", headers=headers)).json() == body


async def test_the_driver_can_open_their_own_documents(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")
    await api.put("/me/driver/documents", files=FILES, headers=headers)

    licence = await api.get("/me/driver/documents/licence", headers=headers)
    insurance = await api.get("/me/driver/documents/insurance", headers=headers)

    assert (licence.status_code, licence.content) == (200, PDF)
    assert licence.headers["content-type"] == "application/pdf"
    assert licence.headers["cache-control"] == "private, no-store"
    assert licence.headers["x-content-type-options"] == "nosniff"
    assert (insurance.content, insurance.headers["content-type"]) == (PNG, "image/png")


async def test_nothing_uploaded_is_404(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")

    response = await api.get("/me/driver/documents/licence", headers=headers)

    assert_problem(response, 404, "document_not_found")


async def test_a_file_thats_not_pdf_jpeg_or_png_is_refused(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")
    renamed = {**FILES, "insurance": ("insurance.pdf", b"MZ\x90\x00 a program", "application/pdf")}

    response = await api.put("/me/driver/documents", files=renamed, headers=headers)

    body = assert_problem(response, 422, "unsupported_file_type")
    assert body["errors"] == [{"field": "insurance", "message": "Must be a PDF, JPEG or PNG"}]
    assert (await api.get("/me/driver", headers=headers)).json()["status"] == "none"


async def test_a_file_over_5_mb_is_refused(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")
    big = PDF + b"0" * MAX_DOCUMENT_BYTES
    too_big = {**FILES, "licence": ("licence.pdf", big, "application/pdf")}

    response = await api.put("/me/driver/documents", files=too_big, headers=headers)

    assert_problem(response, 422, "file_too_large")


async def test_both_files_are_required(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")

    response = await api.put(
        "/me/driver/documents", files={"licence": FILES["licence"]}, headers=headers
    )

    assert_problem(response, 422, "invalid_input")


async def test_an_approved_driver_cant_upload_again(
    api: AsyncClient, session: AsyncSession, log_in: LogIn
) -> None:
    ada, headers = await log_in("ada")
    admin, _ = await log_in("admin", admin=True)
    await api.put("/me/driver/documents", files=FILES, headers=headers)
    drivers = SqlDriverProfileRepository(session)
    profile = await drivers.get(ada.id)
    assert profile is not None
    profile.save_vehicle(Vehicle.create("Honda", "Civic", "Blue", "ABC123"))
    profile.approve(admin.id, datetime.now(UTC))
    await drivers.save(profile)
    await session.commit()

    response = await api.put("/me/driver/documents", files=FILES, headers=headers)

    assert_problem(response, 409, "driver_already_approved")


async def test_an_admin_can_open_a_drivers_documents(api: AsyncClient, log_in: LogIn) -> None:
    ada, headers = await log_in("ada")
    _, admin_headers = await log_in("admin", admin=True)
    await api.put("/me/driver/documents", files=FILES, headers=headers)

    response = await api.get(f"/admin/drivers/{ada.id}/documents/insurance", headers=admin_headers)

    assert (response.status_code, response.content) == (200, PNG)
    assert response.headers["content-type"] == "image/png"


async def test_another_student_cant_open_them(api: AsyncClient, log_in: LogIn) -> None:
    ada, headers = await log_in("ada")
    _, bob_headers = await log_in("bob")
    await api.put("/me/driver/documents", files=FILES, headers=headers)

    # Bob's own documents endpoint only ever shows Bob's files...
    mine = await api.get("/me/driver/documents/licence", headers=bob_headers)
    # ...and the admin endpoint refuses him.
    theirs = await api.get(f"/admin/drivers/{ada.id}/documents/licence", headers=bob_headers)

    assert_problem(mine, 404, "document_not_found")
    assert_problem(theirs, 403, "forbidden")


async def test_an_admin_opening_a_missing_document_gets_404(
    api: AsyncClient, log_in: LogIn
) -> None:
    ada, _ = await log_in("ada")
    _, admin_headers = await log_in("admin", admin=True)

    response = await api.get(f"/admin/drivers/{ada.id}/documents/licence", headers=admin_headers)

    assert_problem(response, 404, "document_not_found")

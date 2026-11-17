"""PUT /me/driver/vehicle (#125) over HTTP, against a real PostgreSQL."""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from accounts.domain.user import User

# The log_in fixture (conftest.py): creates a verified student and logs them in.
LogIn = Callable[..., Awaitable[tuple[User, dict[str, str]]]]

CIVIC = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "abc123"}


async def test_saving_a_vehicle_stores_the_plate_in_uppercase(
    api: AsyncClient, log_in: LogIn
) -> None:
    _, headers = await log_in("ada")

    response = await api.put("/me/driver/vehicle", json=CIVIC, headers=headers)

    assert response.status_code == 200, response.text
    expected = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"}
    assert response.json()["vehicle"] == expected
    assert response.json()["status"] == "none"
    assert (await api.get("/me/driver", headers=headers)).json()["vehicle"] == expected


async def test_saving_again_replaces_the_vehicle(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")
    await api.put("/me/driver/vehicle", json=CIVIC, headers=headers)
    corolla = {"make": "Toyota", "model": "Corolla", "colour": "Grey", "plate": "XYZ9"}

    response = await api.put("/me/driver/vehicle", json=corolla, headers=headers)

    assert response.json()["vehicle"] == corolla


async def test_the_vehicle_is_kept_when_documents_are_uploaded(
    api: AsyncClient, log_in: LogIn
) -> None:
    _, headers = await log_in("ada")
    await api.put("/me/driver/vehicle", json=CIVIC, headers=headers)
    files = {
        "licence": ("licence.pdf", b"%PDF-1.7", "application/pdf"),
        "insurance": ("insurance.pdf", b"%PDF-1.7", "application/pdf"),
    }

    response = await api.put("/me/driver/documents", files=files, headers=headers)

    assert response.json()["status"] == "pending"
    assert response.json()["vehicle"]["plate"] == "ABC123"


async def test_invalid_fields_are_each_named(api: AsyncClient, log_in: LogIn) -> None:
    _, headers = await log_in("ada")

    response = await api.put(
        "/me/driver/vehicle",
        json={"make": "", "model": "Civic", "colour": "Blue", "plate": "ABC 123"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert {error["field"] for error in response.json()["errors"]} == {"make", "plate"}

"""The OpenAPI spec documents each error as it really is (#230): every error response has
its own example, and FastAPI's automatic 422 is documented as a Problem."""

from typing import Any

from fastapi import Cookie, FastAPI
from pydantic import BaseModel, Field

from common_web.app import install


class InvalidFieldOut(BaseModel):
    field: str = Field(examples=["seatsTotal"])
    message: str = Field(examples=["Input should be less than or equal to 6"])


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    errors: list[InvalidFieldOut] | None = None


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


def spec() -> dict[str, Any]:
    app = FastAPI()
    install(app, service="test")

    @app.post(
        "/trips",
        responses={
            401: _problem("Missing or invalid access token", "unauthorized"),
            409: _problem("No seats left on this trip", "no_seats_left"),
            422: _problem("Invalid input; `errors` lists the fields", "invalid_input / bad_seats"),
        },
    )
    async def post_trip(seats: int) -> dict[str, int]:
        return {"seats": seats}

    @app.post("/refresh", responses={401: _problem("Session expired", "invalid_refresh_token")})
    async def refresh(refresh_token: str | None = Cookie(default=None)) -> None:
        return None

    return app.openapi()


def example(document: dict[str, Any], path: str, status: str) -> dict[str, Any]:
    response = document["paths"][path]["post"]["responses"][status]
    result: dict[str, Any] = response["content"]["application/json"]["example"]
    return result


def test_each_error_response_has_its_own_example() -> None:
    document = spec()

    assert example(document, "/trips", "401") == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Missing or invalid access token",
        "instance": "/trips",
        "code": "unauthorized",
        "requestId": "b1e2c3d4e5f6",
    }
    conflict = example(document, "/trips", "409")
    assert conflict["status"] == 409
    assert conflict["code"] == "no_seats_left"
    assert conflict["title"] == "Conflict"
    assert "errors" not in conflict  # only 422s list fields


def test_a_422_example_lists_a_field_from_the_services_own_examples() -> None:
    invalid = example(spec(), "/trips", "422")

    assert invalid["status"] == 422
    assert invalid["code"] == "invalid_input"  # the first of the listed codes
    assert invalid["detail"] == "Invalid input"
    assert invalid["errors"] == [
        {"field": "seatsTotal", "message": "Input should be less than or equal to 6"}
    ]


def test_fastapis_automatic_422_is_documented_as_a_problem() -> None:
    document = spec()
    response = document["paths"]["/refresh"]["post"]["responses"]["422"]
    content = response["content"]["application/json"]

    assert content["schema"] == {"$ref": "#/components/schemas/Problem"}
    assert "(code `invalid_input`)" in response["description"]
    assert content["example"]["code"] == "invalid_input"
    assert "HTTPValidationError" not in document["components"]["schemas"]
    assert "ValidationError" not in document["components"]["schemas"]


def test_the_spec_is_built_once() -> None:
    app = FastAPI()
    install(app, service="test")

    assert app.openapi() is app.openapi()


def test_a_service_without_documented_errors_is_left_alone() -> None:
    app = FastAPI()
    install(app, service="test")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    assert "example" not in str(app.openapi())

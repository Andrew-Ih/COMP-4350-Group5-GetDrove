"""Errors a service raises to produce a clear HTTP error response.

Pure Python: no FastAPI imports, so domain and application code can use them. Each service
subclasses these for its own cases::

    class NoSeatsLeftError(ConflictError):
        code = "no_seats_left"
        title = "No seats left"

    raise NoSeatsLeftError("No seats left on this trip")

``common_web.app`` turns them into Problem Details responses.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class InvalidField:
    """One invalid field, for 422 responses. ``field`` uses the JSON (camelCase) name."""

    field: str
    message: str


class DomainError(Exception):
    """Base for errors that map to an HTTP response.

    Subclasses set ``status``, ``code`` (a short, stable name the frontend can check) and
    ``title`` (a short human summary). The message passed when raising becomes ``detail``.
    """

    status: ClassVar[int] = 400
    code: ClassVar[str] = "bad_request"
    title: ClassVar[str] = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail


class InvalidInputError(DomainError):
    status = 422
    code = "invalid_input"
    title = "Invalid input"

    def __init__(self, detail: str | None = None, errors: list[InvalidField] | None = None) -> None:
        super().__init__(detail)
        self.errors = errors or []


class UnauthorizedError(DomainError):
    status = 401
    code = "unauthorized"
    title = "Not logged in"


class ForbiddenError(DomainError):
    status = 403
    code = "forbidden"
    title = "Not allowed"


class NotFoundError(DomainError):
    status = 404
    code = "not_found"
    title = "Not found"


class ConflictError(DomainError):
    status = 409
    code = "conflict"
    title = "ConflictError"

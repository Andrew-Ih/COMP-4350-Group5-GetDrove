"""Shared web behaviour for every GetDrove service (issue #103).

- Errors: raise a ``DomainError`` subclass anywhere; it becomes a Problem Details
  (RFC 9457) response with the right status.
- Request IDs: every request has one (``X-Request-ID``), returned in the response and
  added to every log line.
- Logging: JSON on the server, readable text locally, using Python's built-in logging.

Only framework-free pieces are imported here, so a service's domain and application layers
can ``from common_web import NotFoundError``. The FastAPI setup lives in ``common_web.app``::

    from common_web.app import install
    install(app, service="trips")
"""

from common_web.context import current_request_id, set_user_id
from common_web.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidField,
    InvalidInputError,
    NotFoundError,
    UnauthorizedError,
)

__all__ = [
    "ConflictError",
    "DomainError",
    "ForbiddenError",
    "InvalidField",
    "InvalidInputError",
    "NotFoundError",
    "UnauthorizedError",
    "current_request_id",
    "set_user_id",
]

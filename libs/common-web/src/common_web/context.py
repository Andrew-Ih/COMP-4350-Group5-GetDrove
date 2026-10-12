"""Per-request context (request ID, user ID), available anywhere in the request's code."""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def current_request_id() -> str | None:
    """The current request's ID: pass it on when calling another service, and use it as
    the ``correlation_id`` when publishing events."""
    return _request_id.get()


def current_user_id() -> str | None:
    return _user_id.get()


def set_user_id(user_id: str | None) -> None:
    """Records the logged-in user's ID for log lines (called by common-security).

    Log the user's ID only: never emails, names or locations.
    """
    _user_id.set(user_id)


def _set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)

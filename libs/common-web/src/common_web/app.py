"""FastAPI wiring: error responses, request IDs and request logging.

Call ``install(app, service="trips")`` once in each service's ``create_app()``.
"""

import logging
import re
import time
import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from common_web.context import _set_request_id
from common_web.errors import DomainError, InvalidInputError
from common_web.logs import configure_logging

REQUEST_ID_HEADER = "X-Request-ID"
PROBLEM_JSON = "application/problem+json"

logger = logging.getLogger("common_web.requests")

# Accept a caller's request ID only if it looks like an ID (no spaces, quotes or newlines
# that could be used to forge log lines).
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def install(app: FastAPI, *, service: str) -> None:
    """Adds logging, request IDs and Problem Details error handling to a service."""
    configure_logging(service)
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)


# ---------------------------------------------------------------- request context


class RequestContextMiddleware:
    """Gives each request an ID, returns it in ``X-Request-ID``, and logs the request once."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        _set_request_id(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"x-request-id" for name, _ in headers):
                    headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _log_request(scope, status_code, started)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            candidate = value.decode("latin-1").strip()
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


def _log_request(scope: Scope, status_code: int, started: float) -> None:
    path = scope.get("path", "")
    if path.endswith("/health"):
        return  # health checks every few seconds would drown everything else
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    level = logging.ERROR if status_code >= 500 else logging.INFO
    logger.log(
        level,
        "%s %s %s",
        scope.get("method", ""),
        path,
        status_code,
        extra={
            "method": scope.get("method"),
            "path": path,
            "status": status_code,
            "duration_ms": duration_ms,
        },
    )


# ---------------------------------------------------------------- error responses


def _problem(
    request: Request,
    status: int,
    *,
    code: str,
    title: str,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail or title,
        "instance": request.url.path,
        "code": code,
        "requestId": request_id,
        **extra,
    }
    response_headers = dict(headers or {})
    if request_id:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=response_headers)


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)
    extra: dict[str, Any] = {}
    if isinstance(error, InvalidInputError) and error.errors:
        extra["errors"] = [{"field": e.field, "message": e.message} for e in error.errors]
    return _problem(
        request, error.status, code=error.code, title=error.title, detail=error.detail, **extra
    )


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    validation = cast(RequestValidationError, exc)
    errors: list[dict[str, str]] = []
    for error in validation.errors():
        location = [str(part) for part in error.get("loc", ())]
        # Drop "body" / "query" / "path" / "header" so the field is the JSON name.
        field = ".".join(location[1:]) if len(location) > 1 else ".".join(location)
        errors.append({"field": field, "message": error.get("msg", "Invalid value")})
    return _problem(
        request,
        422,
        code="invalid_input",
        title="Invalid input",
        detail="Some fields are missing or invalid.",
        errors=errors,
    )


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exc)
    try:
        status = HTTPStatus(http_error.status_code)
        title, code = status.phrase, status.name.lower()
    except ValueError:
        title, code = "Error", "error"
    detail = http_error.detail if http_error.detail != title else None
    return _problem(
        request,
        http_error.status_code,
        code=code,
        title=title,
        detail=detail,
        headers=http_error.headers,
    )


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full details go to the logs only; the response never reveals internals.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _problem(
        request,
        500,
        code="internal_error",
        title="Internal server error",
        detail="Something went wrong on our side. Please try again.",
    )

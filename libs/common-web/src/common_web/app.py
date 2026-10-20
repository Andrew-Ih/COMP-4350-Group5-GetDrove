"""FastAPI wiring: error responses, request IDs and request logging.

Call ``install(app, service="trips")`` once in each service's ``create_app()``.
"""

import json
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
    """Adds logging, request IDs and Problem Details error handling to a service, and
    makes its OpenAPI spec document those errors as they really are."""
    configure_logging(service)
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
    _document_errors(app)


# ---------------------------------------------------------------- OpenAPI error docs

PROBLEM_REF = "#/components/schemas/Problem"
_VALIDATION_REF = "#/components/schemas/HTTPValidationError"
_INVALID_INPUT_DESCRIPTION = "Invalid input; `errors` lists the fields (code `invalid_input`)"
# Routers describe each error as "What went wrong (code `some_code`)".
_CODE_IN_DESCRIPTION = re.compile(r"\s*\(code `([^`]+)`\)")


def _document_errors(app: FastAPI) -> None:
    """Fixes two things in the generated OpenAPI spec (#230):

    - Every error response uses the same ``Problem`` schema, so without an example of its
      own, the docs fill each one in from the schema and show the same body for every
      error. Each error response now gets an example built from its own status and the
      ``(code `...`)`` in its description.
    - FastAPI documents its automatic 422 as ``HTTPValidationError`` (``{"detail": [...]}``),
      but ``install()`` answers invalid input with a ``Problem``. Those 422s now say so.
    """
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        spec = generate()
        _fix_error_responses(spec)
        app.openapi_schema = spec  # built once, like FastAPI's own
        return spec

    app.openapi = openapi  # type: ignore[method-assign]


def _fix_error_responses(spec: dict[str, Any]) -> None:
    schemas: dict[str, Any] = spec.get("components", {}).get("schemas", {})
    if "Problem" not in schemas:
        return  # a service without documented errors: leave its spec alone
    invalid_field = _invalid_field_example(schemas)

    for path, operations in spec.get("paths", {}).items():
        for operation in operations.values():
            for status, response in operation.get("responses", {}).items():
                if not status.isdigit() or int(status) < 400:
                    continue
                content = response.get("content", {}).get("application/json")
                if content is None:
                    continue
                if content.get("schema", {}).get("$ref") == _VALIDATION_REF:
                    content["schema"] = {"$ref": PROBLEM_REF}
                    response["description"] = _INVALID_INPUT_DESCRIPTION
                if content.get("schema", {}).get("$ref") == PROBLEM_REF:
                    description = response.get("description", "")
                    example = _problem_example(int(status), description, path, invalid_field)
                    content.setdefault("example", example)

    # FastAPI's validation schemas are only kept while something still uses them.
    if _VALIDATION_REF not in json.dumps(spec.get("paths", {})):
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)


def _invalid_field_example(schemas: dict[str, Any]) -> dict[str, str]:
    """One entry for a 422's ``errors``, from the service's own InvalidFieldOut examples."""
    properties = schemas.get("InvalidFieldOut", {}).get("properties", {})

    def first(name: str, fallback: str) -> str:
        examples = properties.get(name, {}).get("examples") or [fallback]
        return str(examples[0])

    return {"field": first("field", "fieldName"), "message": first("message", "Field required")}


def _problem_example(
    status: int, description: str, path: str, invalid_field: dict[str, str]
) -> dict[str, Any]:
    match = _CODE_IN_DESCRIPTION.search(description)
    # "invalid_input / email_not_uofm" lists alternatives: the example shows the first.
    code = match.group(1).split("/")[0].strip() if match else "error"
    reason = HTTPStatus(status).phrase
    if status == 422:
        detail = "Invalid input"
    else:
        detail = _CODE_IN_DESCRIPTION.sub("", description) or reason
    example: dict[str, Any] = {
        "type": "about:blank",
        "title": reason,
        "status": status,
        "detail": detail,
        "instance": path,
        "code": code,
        "requestId": "b1e2c3d4e5f6",
    }
    if status == 422:
        example["errors"] = [invalid_field]
    return example


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
        request,
        error.status,
        code=error.code,
        title=error.title,
        detail=error.detail,
        headers=error.headers,
        **extra,
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

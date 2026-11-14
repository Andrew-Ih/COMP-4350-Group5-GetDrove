"""Logging setup with Python's built-in ``logging`` (ADR 0019).

Every log line, including those from Uvicorn, SQLAlchemy and our own libraries, gets the
service name, the current request ID and (once logged in) the user ID. Output is:

- ``LOG_FORMAT=json`` (the server): one JSON object per line, easy to search.
- ``LOG_FORMAT=text`` (default, local): readable lines.

``LOG_LEVEL`` sets the level (default ``INFO``). Add your own fields with ``extra``::

    logger.info("Trip posted", extra={"trip_id": str(trip.id), "seats": 3})

Never log emails, names, addresses or locations; log IDs instead. As a safety net,
coordinates are taken out of every log line anyway (``redact_coordinates``, #31).
"""

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

from common_web.context import current_request_id, current_user_id

# Attributes every LogRecord has; anything else on a record came from ``extra``.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "service",
    "request_id",
    "user_id",
    "taskName",
}

_service_name = "unknown"
_factory_installed = False
_MARKER = "_getdrove_handler"

# A number with 4 or more decimal places: a latitude or longitude to within about 11 m. Riders'
# locations and drivers' places must never be logged (#31), and they can still reach a log
# line through an error message: the database driver and PostgreSQL quote a failed query's
# values, and OSRM's URLs hold coordinates. Ordinary numbers in logs (durations to 0.1 ms,
# version numbers) have fewer decimals. Not when it follows a digit or a ".", or a ":" after a
# digit: that's the seconds of a time ("02:21:55.123456"), not a coordinate. Very short
# durations ("0.004512s") are still taken out; that's harmless.
_COORDINATE = re.compile(r"(?<![\d.])(?<!\d:)-?\d{1,3}\.\d{4,}")
COORDINATE_PLACEHOLDER = "[coordinate]"


def redact_coordinates(text: str) -> str:
    return _COORDINATE.sub(COORDINATE_PLACEHOLDER, text)


def _redact_value(value: Any) -> Any:
    """An ``extra`` field's value with coordinates taken out. Left as it is (a number stays a
    number in JSON) unless it held one, then it becomes the redacted text."""
    if value is None or isinstance(value, bool | int):
        return value
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    redacted = redact_coordinates(text)
    return value if redacted == text else redacted


def _redact(record: logging.LogRecord) -> None:
    """Coordinates out of the message and the traceback, before any handler formats them."""
    try:
        message = record.getMessage()
    except Exception:  # a bad format string: log the raw message rather than lose the line
        message = str(record.msg)
    record.msg, record.args = redact_coordinates(message), ()
    if record.exc_info and record.exc_info[1] is not None:
        # Formatters reuse exc_text instead of formatting the exception again.
        record.exc_text = redact_coordinates(logging.Formatter().formatException(record.exc_info))


def _install_record_factory() -> None:
    """Adds service, request ID and user ID to every record, whichever handler formats it,
    and takes coordinates out of it."""
    global _factory_installed
    if _factory_installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.service = _service_name
        record.request_id = current_request_id()
        record.user_id = current_user_id()
        _redact(record)
        return record

    logging.setLogRecordFactory(factory)
    _factory_installed = True


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": getattr(record, "service", None),
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": getattr(record, "request_id", None),
            "userId": getattr(record, "user_id", None),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                # extra fields: the message was redacted in _redact, these weren't.
                entry[key] = _redact_value(value)
        if record.exc_info:
            # exc_text is the traceback with coordinates taken out (see _redact).
            entry["exception"] = record.exc_text or self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in entry.items() if v is not None}, default=str)


class TextFormatter(logging.Formatter):
    """Readable lines for local development."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(service)s [%(name)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and not key.startswith("_")
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            extras = {"requestId": request_id, **extras}
        if extras:
            line += " " + " ".join(f"{key}={value}" for key, value in extras.items())
        # The whole line, so extra fields are covered too (the message already is).
        return redact_coordinates(line)


def configure_logging(service: str, *, level: str | None = None, fmt: str | None = None) -> None:
    """Sets up logging for a service. Safe to call more than once."""
    global _service_name
    _service_name = service
    _install_record_factory()

    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    fmt = (fmt or os.environ.get("LOG_FORMAT", "text")).lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    setattr(handler, _MARKER, True)

    root = logging.getLogger()
    # Replace only our own handler, so test tools (like pytest's caplog) keep theirs.
    for existing in list(root.handlers):
        if getattr(existing, _MARKER, False):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Send Uvicorn's logs through the same handler. Its access log is replaced by ours
    # (common_web.app logs each request once, with the request ID).
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # httpx logs every outgoing request's URL at INFO, and httpcore its details at DEBUG.
    # Calls between services can carry private data in the URL (OSRM takes the rider's and
    # driver's coordinates in the path), so only their warnings get through, whatever the
    # level. common_web.app already logs each incoming request, without its query string.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)

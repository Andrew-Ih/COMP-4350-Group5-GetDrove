"""Log formatting."""

import json
import logging

import pytest

from common_web.context import _set_request_id, set_user_id
from common_web.logs import JsonFormatter, TextFormatter, configure_logging


def make_record(**extra: object) -> logging.LogRecord:
    logger = logging.getLogger("trips.test")
    return logger.makeRecord(
        "trips.test", logging.INFO, __file__, 1, "Trip posted", None, None, extra=extra
    )


def test_json_lines_include_service_request_and_extra_fields() -> None:
    configure_logging("trips", fmt="json")
    _set_request_id("req-1")
    set_user_id("user-9")
    try:
        record = make_record(trip_id="t-42", seats=3)
    finally:
        _set_request_id(None)
        set_user_id(None)

    line = json.loads(JsonFormatter().format(record))

    assert line["message"] == "Trip posted"
    assert line["level"] == "INFO"
    assert line["service"] == "trips"
    assert line["requestId"] == "req-1"
    assert line["userId"] == "user-9"
    assert line["trip_id"] == "t-42"
    assert line["seats"] == 3
    assert "time" in line


def test_json_lines_leave_out_empty_fields() -> None:
    configure_logging("trips", fmt="json")

    line = json.loads(JsonFormatter().format(make_record()))

    assert "requestId" not in line
    assert "userId" not in line


def test_text_lines_are_readable() -> None:
    configure_logging("trips", fmt="text")
    _set_request_id("req-2")
    try:
        record = make_record(trip_id="t-7")
    finally:
        _set_request_id(None)

    line = TextFormatter().format(record)

    assert "INFO" in line
    assert "trips" in line
    assert "Trip posted" in line
    assert "requestId=req-2" in line
    assert "trip_id=t-7" in line


def test_configure_logging_can_run_twice_without_duplicate_handlers() -> None:
    configure_logging("trips")
    configure_logging("trips")

    ours = [h for h in logging.getLogger().handlers if getattr(h, "_getdrove_handler", False)]
    assert len(ours) == 1


def test_outgoing_request_urls_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """httpx logs each request's URL at INFO, and OSRM URLs hold riders' and drivers'
    coordinates. Only httpx's warnings get through, even at DEBUG."""
    for level in ("INFO", "DEBUG"):
        configure_logging("routing", level=level)

        with caplog.at_level(logging.DEBUG):
            logging.getLogger("httpx").info(
                'HTTP Request: GET http://osrm-foot:5000/table/v1/foot/-97.15,49.85 "200 OK"'
            )
            logging.getLogger("httpcore.http11").debug("send_request_headers.started")
            logging.getLogger("httpx").warning("Connection pool is full")

        messages = [record.getMessage() for record in caplog.records]
        assert messages == ["Connection pool is full"], level
        caplog.clear()

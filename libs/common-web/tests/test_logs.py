"""Log formatting."""

import json
import logging

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

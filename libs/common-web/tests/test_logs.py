"""Log formatting."""

import json
import logging

import pytest

from common_web.context import _set_request_id, set_user_id
from common_web.logs import JsonFormatter, TextFormatter, configure_logging, redact_coordinates


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


# ---------------------------------------------------------------- coordinates (#31)


def test_redact_coordinates_takes_out_latitudes_and_longitudes() -> None:
    text = "invalid input for query argument $1: 'POINT(-97.179137 49.852713)'"

    assert redact_coordinates(text) == (
        "invalid input for query argument $1: 'POINT([coordinate] [coordinate])'"
    )


@pytest.mark.parametrize(
    "text",
    [
        "GET /search 200 duration_ms=12.3",
        "Python 3.13.1",
        "seats=3 cost=4.20",
        "id 1234567",
        # The seconds of a time aren't a coordinate (Andrew's review of #304).
        "departure 2026-11-13T02:21:55.123456+00:00",
        "took 00:01:02.123456",
    ],
)
def test_redact_coordinates_leaves_ordinary_numbers(text: str) -> None:
    assert redact_coordinates(text) == text


@pytest.mark.parametrize(
    "text",
    ["lat:49.852713", "lat=49.852713", "(49.852713, -97.179137)", "foot/-97.179137,49.852713;"],
)
def test_coordinates_right_after_a_colon_or_a_symbol_are_still_taken_out(text: str) -> None:
    """Only a ":" after a digit means a time; "lat:49.852713" is a coordinate."""
    assert "852713" not in redact_coordinates(text)
    assert "179137" not in redact_coordinates(text)


def test_extra_fields_never_contain_coordinates() -> None:
    """Fields passed with ``extra`` skip the message: both formatters still redact them."""
    configure_logging("routing")
    record = logging.getLogger("routing.test").makeRecord(
        "routing.test",
        logging.INFO,
        __file__,
        1,
        "Pickup chosen",
        None,
        None,
        extra={"lat": 49.852713, "where": "POINT(-97.179137 49.852713)", "seats": 3, "ok": True},
    )

    text_line = TextFormatter().format(record)
    json_line = json.loads(JsonFormatter().format(record))  # still valid JSON

    for output in (text_line, json.dumps(json_line)):
        assert "852713" not in output and "179137" not in output
    assert json_line["lat"] == "[coordinate]"
    assert json_line["where"] == "POINT([coordinate] [coordinate])"
    # Other fields keep their type.
    assert (json_line["seats"], json_line["ok"]) == (3, True)


def test_logged_messages_and_tracebacks_never_contain_coordinates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """In the message, in its arguments, and in an exception's text, for every formatter."""
    configure_logging("routing")
    logger = logging.getLogger("routing.test")

    with caplog.at_level(logging.INFO):
        logger.info("Rider at 49.852713, -97.179137")
        logger.info("Rider at %s, %s", 49.852713, -97.179137)
        try:
            raise ValueError("invalid input: 'POINT(-97.179137 49.852713)'")
        except ValueError:
            logger.exception("Unhandled error on POST /internal/matches")

    outputs = [caplog.text] + [
        formatter.format(record)
        for record in caplog.records
        for formatter in (TextFormatter(), JsonFormatter())
    ]
    for output in outputs:
        assert "852713" not in output and "179137" not in output
    assert "Rider at [coordinate], [coordinate]" in caplog.text
    assert "ValueError: invalid input" in caplog.text  # the error itself is still logged

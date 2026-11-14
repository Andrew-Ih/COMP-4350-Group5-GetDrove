"""The contract for Payments being down when requesting a seat (#301): the card check and
the price both need Payments, so the seat request documents its own 503 code for it."""

from trips.infrastructure.main import create_app


def test_seat_request_documents_both_unavailable_codes() -> None:
    request_seat = create_app().openapi()["paths"]["/{trip_id}/requests"]["post"]
    unavailable = request_seat["responses"]["503"]["description"]

    assert "routing_unavailable" in unavailable
    assert "payments_unavailable" in unavailable

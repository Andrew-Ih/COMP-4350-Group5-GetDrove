"""The contract for Accounts being down on the driver's request list (#309): riders' names,
ratings and no-shows come from Accounts, so the list documents its own 503 for it (#139)."""

from trips.infrastructure.main import create_app


def test_driver_request_list_documents_accounts_unavailable() -> None:
    trip_requests = create_app().openapi()["paths"]["/{trip_id}/requests"]["get"]

    assert "accounts_unavailable" in trip_requests["responses"]["503"]["description"]

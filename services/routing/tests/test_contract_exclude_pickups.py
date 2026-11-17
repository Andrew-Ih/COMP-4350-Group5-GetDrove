"""The contract for leaving out rejected pickup points (#292): Trips can send the IDs of
points the rider rejected (#136) so they're never offered again (#29)."""

from typing import Any

import pytest
from pydantic import ValidationError

from routing.adapters.api.schemas import MAX_EXCLUDED_PICKUPS, PickupPointsRequest
from routing.infrastructure.main import create_app

TRIP = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
PICKUPS = {"tripId": TRIP, "rider": {"lat": 49.8722, "lng": -97.1561}}


def test_exclude_is_optional_and_empty_by_default() -> None:
    assert PickupPointsRequest.model_validate(PICKUPS).exclude == []


def test_exclude_takes_pickup_point_ids() -> None:
    request = PickupPointsRequest.model_validate({**PICKUPS, "exclude": ["s42", "s45"]})

    assert request.exclude == ["s42", "s45"]


@pytest.mark.parametrize(
    "exclude",
    [
        [f"s{n}" for n in range(MAX_EXCLUDED_PICKUPS + 1)],  # more than 20
        [""],  # an empty ID
        ["s" * 65],  # longer than any ID
        "s42",  # not a list
    ],
)
def test_invalid_exclude_lists_are_rejected(exclude: Any) -> None:
    with pytest.raises(ValidationError):
        PickupPointsRequest.model_validate({**PICKUPS, "exclude": exclude})


def test_twenty_ids_is_the_limit() -> None:
    exclude = [f"s{n}" for n in range(MAX_EXCLUDED_PICKUPS)]

    assert len(PickupPointsRequest.model_validate({**PICKUPS, "exclude": exclude}).exclude) == 20


def test_spec_documents_exclude() -> None:
    schema = create_app().openapi()["components"]["schemas"]["PickupPointsRequest"]
    exclude = schema["properties"]["exclude"]

    assert exclude["maxItems"] == MAX_EXCLUDED_PICKUPS
    assert "exclude" not in schema.get("required", [])

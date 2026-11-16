"""The #70 runtime resolves trusted references without the #151 database."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from payments.adapters.configured_cards import (
    ConfiguredSavedCardLookup,
    SavedCardNotConfiguredError,
)
from payments.domain.holds import SavedPaymentCard
from payments.infrastructure.settings import Settings


async def test_lookup_is_per_rider_and_unknown_is_not_reported_as_no_card() -> None:
    rider = uuid4()
    card = SavedPaymentCard("cus_one", "pm_one")
    lookup = ConfiguredSavedCardLookup({rider: card})
    assert await lookup.for_rider(rider) == card
    with pytest.raises(SavedCardNotConfiguredError):
        await lookup.for_rider(uuid4())


def test_settings_read_the_reference_map_without_exposing_it_in_repr(monkeypatch) -> None:
    import json

    rider = uuid4()
    monkeypatch.setenv(
        "PAYMENTS_SAVED_CARD_REFERENCES",
        json.dumps({str(rider): {"customer_id": "cus_test", "payment_method_id": "pm_test"}}),
    )
    settings = Settings(_env_file=None)
    assert settings.saved_card_references[rider] == SavedPaymentCard("cus_test", "pm_test")
    assert "cus_test" not in repr(settings)


@pytest.mark.parametrize("customer,method", [("wrong", "pm_test"), ("cus_test", "wrong")])
def test_invalid_reference_configuration_is_rejected(customer: str, method: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, saved_card_references={uuid4(): SavedPaymentCard(customer, method)}
        )

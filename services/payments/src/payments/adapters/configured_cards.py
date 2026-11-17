"""Explicit per-rider Stripe references for the test-mode hold processor.

This does not create customers, save cards, or depend on #151's tables.
"""

from collections.abc import Mapping
from uuid import UUID

from payments.domain.holds import SavedPaymentCard


class SavedCardNotConfiguredError(Exception):
    """No trusted mapping is configured; this is not proof the rider has no card."""


class ConfiguredSavedCardLookup:
    def __init__(self, references: Mapping[UUID, SavedPaymentCard]) -> None:
        self._references = dict(references)

    async def for_rider(self, rider_id: UUID) -> SavedPaymentCard:
        try:
            return self._references[rider_id]
        except KeyError:
            raise SavedCardNotConfiguredError(
                "Saved-card reference is not configured for this rider"
            ) from None

"""Events shared between services: the event contracts (issues #108, #262).

Each event is an ``EventPayload`` subclass in the module for the service that publishes it.
Producers and consumers both import it from here, so they always agree on its shape, and
``scripts/export_openapi.py`` writes its JSON Schema to ``contracts/events/``.

Rules: payloads carry IDs and only the data consumers need; adding an optional field keeps
the version; renaming or removing a field means a new version.
"""

from events.catalog.accounts import (
    DriverApproved,
    DriverRejected,
    UserRegistered,
    VerificationEmailRequested,
)
from events.catalog.payments import PaymentFailed, PaymentHeld, PaymentReleased
from events.catalog.trips import (
    DriverLateCancellation,
    RequestAccepted,
    RequestCancelled,
    RequestDeclined,
    SeatRequested,
    TripCancelled,
    TripPosted,
)
from events.envelope import EventPayload

ALL_EVENTS: list[type[EventPayload]] = [
    UserRegistered,
    VerificationEmailRequested,
    DriverApproved,
    DriverRejected,
    TripPosted,
    SeatRequested,
    RequestAccepted,
    RequestDeclined,
    RequestCancelled,
    TripCancelled,
    DriverLateCancellation,
    PaymentHeld,
    PaymentFailed,
    PaymentReleased,
]

__all__ = [
    "ALL_EVENTS",
    "DriverApproved",
    "DriverLateCancellation",
    "DriverRejected",
    "PaymentFailed",
    "PaymentHeld",
    "PaymentReleased",
    "RequestAccepted",
    "RequestCancelled",
    "RequestDeclined",
    "SeatRequested",
    "TripCancelled",
    "TripPosted",
    "UserRegistered",
    "VerificationEmailRequested",
]

"""Errors raised when managing trips."""

from common_web.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidField,
    InvalidInputError,
    NotFoundError,
)


class NotTripDriverError(ForbiddenError):
    code = "not_trip_driver"
    title = "Only the trip's driver can cancel it"


class SeriesNotFoundError(NotFoundError):
    code = "series_not_found"
    title = "Series not found"

    def __init__(self) -> None:
        super().__init__("No series with this ID")


class TripNotCancellableError(ConflictError):
    code = "trip_not_cancellable"
    title = "The trip has already started, finished or been cancelled"


class DepartureInPastError(InvalidInputError):
    code = "departure_in_past"
    title = "Departure time is in the past"

    def __init__(self) -> None:
        super().__init__(
            "Departure time must be in the future",
            errors=[InvalidField(field="departureAt", message="Must be in the future")],
        )


class RoutingInvalidLocationError(InvalidInputError):
    def __init__(self) -> None:
        message = "We couldn't find a driving route from this place."
        super().__init__(
            message,
            errors=[InvalidField(field="place", message=message)],
        )


class RoutingUnavailableError(DomainError):
    status = 503
    code = "routing_unavailable"
    title = "Routing unavailable"

    def __init__(
        self, detail: str = "Could not calculate a driving route. Please try again."
    ) -> None:
        super().__init__(detail)


class PricingUnavailableError(Exception):
    """Payments couldn't price a rider's share. Search still shows the trip, without a cost,
    so this never becomes an HTTP error."""


class DriverNotApprovedError(ForbiddenError):
    """Only approved drivers can post trips (#11). Approval is in Accounts: the driver
    uploads their documents, and an admin approves them (403)."""

    code = "driver_not_approved"
    title = "Not approved to drive"

    def __init__(self) -> None:
        super().__init__(
            "You need to be approved to drive before posting a trip. Upload your licence and "
            "insurance on your driver page; an admin will review them."
        )


class TripNotFoundError(NotFoundError):
    code = "trip_not_found"
    title = "Trip not found"

    def __init__(self) -> None:
        super().__init__("No trip with this ID")

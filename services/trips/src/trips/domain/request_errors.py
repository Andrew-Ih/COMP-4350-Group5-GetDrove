"""Errors raised when a rider requests a seat."""

from common_web.errors import DomainError, InvalidField, InvalidInputError


class TripNotFoundError(DomainError):
    status = 404
    code = "trip_not_found"
    title = "Trip not found"

    def __init__(self, detail: str = "No trip with this ID.") -> None:
        super().__init__(detail)


class OwnTripError(DomainError):
    status = 403
    code = "own_trip"
    title = "You cannot request a seat on your own trip"

    def __init__(self, detail: str = "You cannot request a seat on your own trip.") -> None:
        super().__init__(detail)


class TripNotOpenError(DomainError):
    status = 409
    code = "trip_not_open"
    title = "Trip is not open for requests"

    def __init__(self, detail: str = "This trip is not open for seat requests.") -> None:
        super().__init__(detail)


class TripFullError(DomainError):
    status = 409
    code = "trip_full"
    title = "No seats left"

    def __init__(self, detail: str = "This trip has no seats left.") -> None:
        super().__init__(detail)


class AlreadyRequestedError(DomainError):
    status = 409
    code = "already_requested"
    title = "Already requested"

    def __init__(self, detail: str = "You already have a request on this trip.") -> None:
        super().__init__(detail)


class OverlappingRequestError(DomainError):
    status = 409
    code = "overlapping_request"
    title = "Overlapping request"

    def __init__(self, detail: str = "You already have a request that overlaps this trip.") -> None:
        super().__init__(detail)


class CardRequiredError(DomainError):
    status = 409
    code = "card_required"
    title = "Saved card required"

    def __init__(self, detail: str = "Save a payment card before requesting a seat.") -> None:
        super().__init__(detail)


class PaymentsUnavailableError(DomainError):
    status = 503
    code = "payments_unavailable"
    title = "Payments unavailable"

    def __init__(self) -> None:
        super().__init__("The price or saved card can't be checked right now. Please try again.")


class CardStatusUnavailableError(Exception):
    """Payments could not reliably determine whether the rider has a saved card."""


class PickupNotAvailableError(InvalidInputError):
    code = "pickup_not_available"
    title = "Pickup point unavailable"

    def __init__(self) -> None:
        message = "Choose an available pickup point from this trip's pickup options."
        super().__init__(
            message,
            errors=[InvalidField(field="pickupId", message=message)],
        )


class SeatTakenError(DomainError):
    status = 409
    code = "seat_taken"
    title = "No seat left"

    def __init__(self, detail: str = "The last seat on this trip was just taken.") -> None:
        super().__init__(detail)


class RequestNotPendingError(DomainError):
    status = 409
    code = "request_not_pending"
    title = "Request is not pending"

    def __init__(self, detail: str = "Only a pending request can be accepted.") -> None:
        super().__init__(detail)


class RequestNotDecidableError(DomainError):
    status = 409
    code = "request_not_decidable"
    title = "Request cannot be declined"

    def __init__(self, detail: str = "Only a pending or accepted request can be declined.") -> None:
        super().__init__(detail)


class RequestNotCancellableError(DomainError):
    status = 409
    code = "request_not_cancellable"
    title = "Request cannot be cancelled"

    def __init__(
        self, detail: str = "Only a pending or accepted request can be cancelled."
    ) -> None:
        super().__init__(detail)


class NotYourRequestError(DomainError):
    status = 403
    code = "not_your_request"
    title = "Not your request"

    def __init__(self, detail: str = "Only the rider who made this request can cancel it.") -> None:
        super().__init__(detail)


class RequestNotFoundError(DomainError):
    status = 404
    code = "request_not_found"
    title = "Request not found"

    def __init__(self, detail: str = "No request with this ID.") -> None:
        super().__init__(detail)


class NotTripDriverError(DomainError):
    status = 403
    code = "not_trip_driver"
    title = "Not the trip's driver"

    def __init__(self, detail: str = "Only the trip's driver can do this.") -> None:
        super().__init__(detail)


class AccountsUnavailableError(DomainError):
    status = 503
    code = "accounts_unavailable"
    title = "Accounts unavailable"

    def __init__(
        self, detail: str = "The riders' details can't be loaded right now. Please try again."
    ) -> None:
        super().__init__(detail)

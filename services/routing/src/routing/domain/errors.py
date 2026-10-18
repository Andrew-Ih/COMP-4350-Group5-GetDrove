"""Errors raised when computing a route."""

from common_web.errors import DomainError, InvalidField, InvalidInputError


class NoRouteError(InvalidInputError):
    """OSRM can't drive between the two points (e.g. one is nowhere near a road)."""

    def __init__(self) -> None:
        message = "No driving route between the origin and the destination."
        super().__init__(
            message,
            errors=[
                InvalidField(field="origin", message=message),
                InvalidField(field="destination", message=message),
            ],
        )


class RoutingEngineUnavailableError(DomainError):
    status = 503
    code = "routing_engine_unavailable"
    title = "Routing engine unavailable"

    def __init__(self) -> None:
        super().__init__("The routing engine is unavailable or too slow. Please try again.")

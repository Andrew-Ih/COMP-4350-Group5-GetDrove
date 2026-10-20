"""Application use case for reading a trip's stored route, for the map (#123)."""

from uuid import UUID

from routing.application.ports import RouteRepository
from routing.domain.entities import Route
from routing.domain.errors import RouteNotFoundError


class GetRoute:
    def __init__(self, repository: RouteRepository) -> None:
        self.repository = repository

    async def execute(self, trip_id: UUID) -> Route:
        # Sprint 1 returns the full route to any logged-in user. From Sprint 2, riders get
        # it from their pickup point on, so the driver's start stays private.
        route = await self.repository.get(trip_id)

        if route is None:
            raise RouteNotFoundError()

        return route

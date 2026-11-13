"""Application use case for reading a trip's stored route, for the map (#123, #135)."""

from dataclasses import replace
from uuid import UUID

from routing.application.ports import RouteRepository
from routing.domain.entities import Route
from routing.domain.errors import RouteNotFoundError
from routing.domain.privacy import visible_path


class GetRoute:
    def __init__(self, repository: RouteRepository) -> None:
        self.repository = repository

    async def execute(self, trip_id: UUID, viewer_id: UUID) -> Route:
        """The trip's route as ``viewer_id`` may see it: all of it for the driver, without the
        driver's own end for anyone else (``routing.domain.privacy``)."""
        route = await self.repository.get(trip_id)

        if route is None:
            raise RouteNotFoundError()

        return replace(route, path=visible_path(route, viewer_id))

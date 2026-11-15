"""Application use case for computing and storing a trip's driving route (#24)."""

from uuid import UUID

from routing.application.ports import RouteRepository, RoutingEngine
from routing.domain.corridor import sample_route
from routing.domain.entities import Route
from routing.domain.values import LatLng


class ComputeRoute:
    def __init__(self, engine: RoutingEngine, repository: RouteRepository) -> None:
        self.engine = engine
        self.repository = repository

    async def execute(self, trip_id: UUID, origin: LatLng, destination: LatLng) -> Route:
        driving = await self.engine.driving_route(origin, destination)

        route = Route(
            trip_id=trip_id,
            path=driving.path,
            distance_meters=driving.distance_meters,
            duration_seconds=driving.duration_seconds,
        )

        # Stored with the route, so riders along it can be found by its corridor (#25).
        await self.repository.save(route, sample_route(route))

        return route

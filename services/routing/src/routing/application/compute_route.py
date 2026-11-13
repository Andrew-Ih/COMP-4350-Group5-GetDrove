"""Application use case for computing and storing a trip's driving route (#24)."""

from uuid import UUID

from routing.application.ports import RouteRepository, RoutingEngine
from routing.domain.corridor import sample_route
from routing.domain.entities import Route
from routing.domain.values import Direction, LatLng


class ComputeRoute:
    def __init__(self, engine: RoutingEngine, repository: RouteRepository) -> None:
        self.engine = engine
        self.repository = repository

    async def execute(
        self,
        trip_id: UUID,
        origin: LatLng,
        destination: LatLng,
        driver_id: UUID | None = None,
        direction: Direction | None = None,
    ) -> Route:
        """``driver_id`` and ``direction`` decide who sees the whole route on the map (#135).
        Trips sends them from Sprint 2; without them both ends are hidden from everyone."""
        driving = await self.engine.driving_route(origin, destination)

        route = Route(
            trip_id=trip_id,
            path=driving.path,
            distance_meters=driving.distance_meters,
            duration_seconds=driving.duration_seconds,
            driver_id=driver_id,
            direction=direction,
        )

        # Stored with the route, so riders along it can be found by its corridor (#25).
        await self.repository.save(route, sample_route(route))

        return route

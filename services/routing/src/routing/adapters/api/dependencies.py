"""Dependencies for Routing API handlers."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from routing.adapters.osrm import OSRMRoutingEngine
from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.application.compute_route import ComputeRoute
from routing.application.get_route import GetRoute
from routing.domain.entities import Route
from routing.domain.values import LatLng


class ComputeRouteCommand:
    """Runs route computation within a database transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        engine: OSRMRoutingEngine,
    ) -> None:
        self.session_factory = session_factory
        self.engine = engine

    async def execute(self, *, trip_id: UUID, origin: LatLng, destination: LatLng) -> Route:
        async with self.session_factory() as session:
            use_case = ComputeRoute(self.engine, SQLAlchemyRouteRepository(session))

            async with session.begin():
                return await use_case.execute(
                    trip_id=trip_id,
                    origin=origin,
                    destination=destination,
                )


def get_compute_route(request: Request) -> ComputeRouteCommand:
    return ComputeRouteCommand(
        session_factory=request.app.state.session_factory,
        engine=OSRMRoutingEngine(request.app.state.osrm_car_client),
    )


ComputeRouteService = Annotated[ComputeRouteCommand, Depends(get_compute_route)]


class GetRouteQuery:
    """Reads a trip's route in its own database session."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def execute(self, trip_id: UUID) -> Route:
        async with self.session_factory() as session:
            return await GetRoute(SQLAlchemyRouteRepository(session)).execute(trip_id)


def get_get_route(request: Request) -> GetRouteQuery:
    return GetRouteQuery(session_factory=request.app.state.session_factory)


GetRouteService = Annotated[GetRouteQuery, Depends(get_get_route)]

"""Creates the FastAPI app for the routing service.

To run it locally, see the service README.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.dependencies import install_security
from common_web.app import install
from routing.adapters.api import health, routing_router
from routing.domain.values import Corridor
from routing.infrastructure.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close infrastructure resources."""

    settings = get_settings()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.corridor = Corridor(radius_meters=settings.corridor_meters)
    app.state.max_walk_seconds = settings.max_walk_seconds

    async with (
        httpx.AsyncClient(
            base_url=settings.osrm_car_url, timeout=settings.osrm_timeout_seconds
        ) as osrm_car_client,
        httpx.AsyncClient(
            base_url=settings.osrm_foot_url, timeout=settings.osrm_timeout_seconds
        ) as osrm_foot_client,
    ):
        app.state.osrm_car_client = osrm_car_client
        app.state.osrm_foot_client = osrm_foot_client
        try:
            yield
        finally:
            await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove routing service",
        version="0.1.0",
        lifespan=lifespan,
    )
    install(app, service="routing")
    install_security(app)
    app.include_router(health.router)
    app.include_router(routing_router.internal_router)
    app.include_router(routing_router.public_router)
    return app


app = create_app()

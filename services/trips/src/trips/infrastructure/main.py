"""Creates the FastAPI app for the trips service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from common_security.dependencies import install_security
from common_web.app import install
from trips.adapters.api import health, trips_router
from trips.infrastructure.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close infrastructure resources."""

    settings = get_settings()

    engine = create_async_engine(settings.database_url)

    app.state.session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with httpx.AsyncClient(
        base_url=settings.routing_url,
        timeout=5.0,
    ) as routing_client:
        app.state.routing_client = routing_client

        try:
            yield
        finally:
            await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove trips service",
        version="0.1.0",
        lifespan=lifespan,
    )

    install(app, service="trips")
    install_security(app)

    app.include_router(health.router)
    app.include_router(trips_router.router)

    return app


app = create_app()

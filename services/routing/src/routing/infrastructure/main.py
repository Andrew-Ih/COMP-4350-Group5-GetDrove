"""Creates the FastAPI app for the routing service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from routing.adapters.api import health, routing_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove routing service",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(routing_router.internal_router)
    app.include_router(routing_router.public_router)
    return app


app = create_app()

"""Creates the FastAPI app for the trips service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from common_web.app import install
from trips.adapters.api import health, trips_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove trips service",
        version="0.1.0",
    )
    install(app, service="trips")
    app.include_router(health.router)
    app.include_router(trips_router.router)
    return app


app = create_app()

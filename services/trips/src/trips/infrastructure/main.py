"""Creates the FastAPI app for the trips service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from trips.adapters.api import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove trips service",
        version="0.1.0",
    )
    app.include_router(health.router)
    return app


app = create_app()

"""Creates the FastAPI app for the accounts service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from accounts.adapters.api import auth_router, health
from accounts.adapters.security.signing_key import load_signing_key
from accounts.infrastructure.settings import get_settings
from common_security.dependencies import install_security
from common_security.keys import StaticKeys
from common_web.app import install


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove accounts service",
        version="0.1.0",
    )
    install(app, service="accounts")

    # Accounts signs tokens and checks its own tokens with the same key (no JWKS fetch).
    settings = get_settings()
    signing_key = load_signing_key(settings.jwt_private_key, environment=settings.environment)
    app.state.signing_key = signing_key
    install_security(app, keys=StaticKeys(signing_key.jwks()))

    app.include_router(health.router)
    app.include_router(auth_router.auth_router)
    app.include_router(auth_router.users_router)
    app.include_router(auth_router.keys_router)
    return app


app = create_app()

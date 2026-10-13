"""Access-token checking for every GetDrove service (issue #91, ADR 0006).

Accounts signs access tokens with its private key and publishes the public key at
``/.well-known/jwks.json``. Each service fetches that key once, caches it, and checks every
token itself, so no service calls Accounts on each request.

In a service::

    # infrastructure/main.py
    from common_security.dependencies import install_security
    install_security(app)

    # adapters/api/..._router.py
    from common_security.dependencies import AuthenticatedUser, require_role

    @router.post("/")
    async def post_trip(body: PostTripRequest, user: AuthenticatedUser) -> Trip: ...

Only framework-free pieces are imported here (``CurrentUser``), so domain and application
code can use the type without importing FastAPI.
"""

from common_security.user import CurrentUser

__all__ = ["CurrentUser"]

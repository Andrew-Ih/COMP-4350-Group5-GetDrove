"""Settings for checking tokens, from environment variables (prefix ``AUTH_``)."""

import os
from dataclasses import dataclass

ISSUER = "getdrove-accounts"
AUDIENCE = "getdrove"


@dataclass(frozen=True)
class AuthSettings:
    jwks_url: str = "http://localhost:8001/.well-known/jwks.json"
    issuer: str = ISSUER
    audience: str = AUDIENCE
    leeway_seconds: int = 30  # allowed clock difference between servers
    cache_seconds: int = 600  # how long the public keys are cached
    refetch_min_seconds: int = 60  # unknown key ID: re-fetch at most this often

    @classmethod
    def from_env(cls) -> "AuthSettings":
        """``AUTH_JWKS_URL`` is the one that differs: Docker Compose sets it to
        http://accounts:8000/.well-known/jwks.json; running locally with uv it defaults to
        Accounts on port 8001."""
        return cls(jwks_url=os.environ.get("AUTH_JWKS_URL", cls.jwks_url))

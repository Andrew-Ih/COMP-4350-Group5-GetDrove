"""Where the public keys for checking tokens come from."""

import asyncio
import logging
import time
from collections.abc import Iterable
from typing import Any, Protocol

import httpx
import jwt

from common_security.config import AuthSettings
from common_security.errors import AuthUnavailableError

logger = logging.getLogger(__name__)


class KeySource(Protocol):
    async def get_key(self, kid: str) -> jwt.PyJWK | None:
        """The public key with this key ID, or None if there isn't one."""
        ...


class StaticKeys:
    """A fixed set of keys: Accounts' own key, or test keys."""

    def __init__(self, jwks: dict[str, Any] | Iterable[jwt.PyJWK]) -> None:
        keys = jwt.PyJWKSet.from_dict(jwks).keys if isinstance(jwks, dict) else list(jwks)
        self._keys = {key.key_id: key for key in keys if key.key_id}

    async def get_key(self, kid: str) -> jwt.PyJWK | None:
        return self._keys.get(kid)


class JwksClient:
    """Fetches Accounts' JWKS and caches it.

    - Cached for ``cache_seconds`` (10 minutes).
    - A token with an unknown key ID (Accounts rotated its key) triggers an immediate
      re-fetch, at most once per ``refetch_min_seconds``, so bad tokens can't flood Accounts.
    - If Accounts can't be reached, cached keys keep working; with no cached keys, requests
      get 503 ``auth_unavailable``.
    """

    def __init__(
        self, settings: AuthSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str) -> jwt.PyJWK | None:
        now = time.monotonic()
        if not self._keys or now - self._fetched_at > self._settings.cache_seconds:
            await self._refresh(required=not self._keys)
        elif kid not in self._keys and now - self._fetched_at > self._settings.refetch_min_seconds:
            await self._refresh(required=False)
        return self._keys.get(kid)

    async def _refresh(self, *, required: bool) -> None:
        async with self._lock:
            try:
                async with httpx.AsyncClient(timeout=3.0, transport=self._transport) as client:
                    response = await client.get(self._settings.jwks_url)
                    response.raise_for_status()
                    key_set = jwt.PyJWKSet.from_dict(response.json())
            except (httpx.HTTPError, ValueError, jwt.PyJWKSetError) as exc:
                logger.warning("Couldn't fetch JWKS from %s: %s", self._settings.jwks_url, exc)
                if required:
                    raise AuthUnavailableError(
                        "Can't check logins right now. Try again shortly."
                    ) from exc
                return
            self._keys = {key.key_id: key for key in key_set.keys if key.key_id}
            self._fetched_at = time.monotonic()

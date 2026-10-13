"""Fetching and caching Accounts' public keys."""

import httpx
import pytest

from common_security.config import AuthSettings
from common_security.errors import AuthUnavailableError
from common_security.keys import JwksClient
from common_security.testing import TestAuth


def serve(auth: TestAuth, calls: list[str], *, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(status, json=auth.jwks)

    return httpx.MockTransport(handler)


async def test_keys_are_fetched_once_and_cached() -> None:
    auth, calls = TestAuth(), []
    client = JwksClient(AuthSettings(jwks_url="http://accounts/jwks"), transport=serve(auth, calls))

    assert await client.get_key(auth.kid) is not None
    assert await client.get_key(auth.kid) is not None
    assert calls == ["http://accounts/jwks"]


async def test_unknown_key_id_is_rate_limited() -> None:
    auth, calls = TestAuth(), []
    client = JwksClient(AuthSettings(jwks_url="http://accounts/jwks"), transport=serve(auth, calls))

    await client.get_key(auth.kid)
    assert await client.get_key("rotated-key") is None
    assert await client.get_key("rotated-key") is None
    assert len(calls) == 1  # within refetch_min_seconds: no flood of requests to Accounts


async def test_unknown_key_id_triggers_a_refetch_after_the_minimum_interval() -> None:
    auth, calls = TestAuth(), []
    settings = AuthSettings(jwks_url="http://accounts/jwks", refetch_min_seconds=0)
    client = JwksClient(settings, transport=serve(auth, calls))

    await client.get_key(auth.kid)
    await client.get_key("rotated-key")

    assert len(calls) == 2


async def test_accounts_down_with_no_cached_keys_is_503() -> None:
    client = JwksClient(
        AuthSettings(jwks_url="http://accounts/jwks"), transport=serve(TestAuth(), [], status=500)
    )

    with pytest.raises(AuthUnavailableError):
        await client.get_key("any")

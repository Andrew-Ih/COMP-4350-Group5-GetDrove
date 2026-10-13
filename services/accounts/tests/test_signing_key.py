"""Accounts' signing key and the JWKS endpoint."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from httpx import ASGITransport, AsyncClient

from accounts.adapters.security.signing_key import (
    SigningKey,
    SigningKeyMissingError,
    load_signing_key,
)
from accounts.infrastructure.main import create_app
from common_security.config import AUDIENCE, ISSUER
from common_security.keys import StaticKeys
from common_security.validator import TokenValidator


def test_production_refuses_to_start_without_a_key() -> None:
    with pytest.raises(SigningKeyMissingError):
        load_signing_key(None, environment="production")


def test_development_generates_a_temporary_key() -> None:
    assert isinstance(load_signing_key(None, environment="development"), SigningKey)


def test_key_is_loaded_from_pem() -> None:
    original = SigningKey.generate()
    pem = original.private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    loaded = load_signing_key(pem, environment="production")

    assert loaded.kid == original.kid


def test_published_key_has_no_private_parts() -> None:
    jwk = SigningKey.generate().public_jwk()

    assert set(jwk) == {"kty", "kid", "use", "alg", "n", "e"}


async def test_tokens_signed_by_accounts_validate_against_its_jwks() -> None:
    key = SigningKey.generate()
    now = int(time.time())
    claims = {
        "sub": str(uuid.uuid4()),
        "roles": ["user"],
        "iat": now,
        "exp": now + 900,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    token = jwt.encode(claims, key.private_key, algorithm="RS256", headers={"kid": key.kid})

    user = await TokenValidator(StaticKeys(key.jwks())).validate(token)

    assert str(user.id) == claims["sub"]


async def test_jwks_endpoint_serves_the_public_key() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/.well-known/jwks.json")

    assert response.status_code == 200
    keys = response.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["kid"] == app.state.signing_key.kid
    assert "d" not in keys[0]

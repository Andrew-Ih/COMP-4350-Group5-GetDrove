"""JwtAccessTokenIssuer (#6): the tokens must pass the same common_security checks every
other service runs, so Trips and the rest accept them."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from accounts.adapters.security.access_tokens import JwtAccessTokenIssuer
from accounts.adapters.security.signing_key import SigningKey
from accounts.domain.email import Email
from accounts.domain.user import User
from common_security.errors import InvalidTokenError, TokenExpiredError
from common_security.keys import StaticKeys
from common_security.validator import TokenValidator

KEY = SigningKey.generate()
issuer = JwtAccessTokenIssuer(KEY)
validator = TokenValidator(StaticKeys(KEY.jwks()))


def ada(*, admin: bool = False) -> User:
    user = User.register(Email.parse("ada@myumanitoba.ca"), "hash", "Ada", "Lovelace")
    user.is_admin = admin
    return user


async def test_a_token_passes_the_checks_every_service_runs() -> None:
    user = ada()

    current = await validator.validate(issuer.issue(user, datetime.now(UTC)))

    assert current.id == user.id
    assert current.roles == frozenset({"user"})


async def test_an_admins_token_carries_both_roles() -> None:
    current = await validator.validate(issuer.issue(ada(admin=True), datetime.now(UTC)))

    assert current.roles == frozenset({"user", "admin"})


def test_a_token_lasts_15_minutes() -> None:
    now = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
    claims = jwt.decode(issuer.issue(ada(), now), options={"verify_signature": False})

    assert claims["exp"] - claims["iat"] == 900
    assert issuer.lifetime == timedelta(seconds=900)


def test_a_token_carries_only_the_agreed_claims() -> None:
    """No email or name: other services only see the user ID and roles."""
    token = issuer.issue(ada(), datetime.now(UTC))

    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) == {"sub", "roles", "iat", "exp", "iss", "aud"}
    assert jwt.get_unverified_header(token) == {"alg": "RS256", "kid": KEY.kid, "typ": "JWT"}


async def test_a_token_stops_working_after_15_minutes() -> None:
    issued = datetime.now(UTC) - timedelta(minutes=16)  # past 15 minutes plus the 30 s leeway

    with pytest.raises(TokenExpiredError):
        await validator.validate(issuer.issue(ada(), issued))


async def test_a_token_from_another_key_is_refused() -> None:
    other = JwtAccessTokenIssuer(SigningKey.generate())

    with pytest.raises(InvalidTokenError):
        await validator.validate(other.issue(ada(), datetime.now(UTC)))

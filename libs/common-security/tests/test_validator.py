"""Token checking, without FastAPI."""

import secrets
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from common_security.errors import InvalidTokenError, TokenExpiredError
from common_security.testing import TestAuth


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


async def test_valid_token_gives_the_user(auth: TestAuth) -> None:
    user_id = uuid.uuid4()

    user = await auth.validator().validate(auth.token(user_id=user_id, roles=["user", "admin"]))

    assert user.id == user_id
    assert user.roles == {"user", "admin"}
    assert user.has_role("admin")


async def test_expired_token_is_rejected(auth: TestAuth) -> None:
    with pytest.raises(TokenExpiredError):
        await auth.validator().validate(auth.token(expires_in=-120))


async def test_token_expired_within_the_leeway_is_accepted(auth: TestAuth) -> None:
    user = await auth.validator().validate(auth.token(expires_in=-10))

    assert user.id == auth.user_id


@pytest.mark.parametrize(
    "overrides",
    [{"aud": "someone-else"}, {"iss": "someone-else"}, {"sub": "not-a-uuid"}, {"roles": "admin"}],
)
async def test_wrong_claims_are_rejected(auth: TestAuth, overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(auth.token(**overrides))


async def test_token_signed_by_another_key_is_rejected(auth: TestAuth) -> None:
    impostor = TestAuth(kid=auth.kid)  # same key ID, different key

    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(impostor.token())


async def test_unknown_key_id_is_rejected(auth: TestAuth) -> None:
    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(TestAuth(kid="other").token())


async def test_unsigned_token_is_rejected(auth: TestAuth) -> None:
    token = jwt.encode(
        {"sub": str(auth.user_id)}, key=None, algorithm="none", headers={"kid": auth.kid}
    )

    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(token)


async def test_symmetric_algorithm_is_rejected(auth: TestAuth) -> None:
    # A classic attack: sign with HS256 using the public key as the secret.
    secret = secrets.token_hex(32)
    token = jwt.encode(
        {"sub": str(auth.user_id)}, secret, algorithm="HS256", headers={"kid": auth.kid}
    )

    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(token)


async def test_missing_expiry_is_rejected(auth: TestAuth) -> None:
    claims = {
        "sub": str(auth.user_id),
        "roles": ["user"],
        "iat": 0,
        "iss": "getdrove-accounts",
        "aud": "getdrove",
    }
    token = jwt.encode(claims, auth.private_key, algorithm="RS256", headers={"kid": auth.kid})

    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(token)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
async def test_garbage_is_rejected(auth: TestAuth, token: str) -> None:
    with pytest.raises(InvalidTokenError):
        await auth.validator().validate(token)


def test_test_keys_are_rsa(auth: TestAuth) -> None:
    assert isinstance(auth.private_key, rsa.RSAPrivateKey)
    assert "d" not in auth.jwks["keys"][0]  # the published key has no private part

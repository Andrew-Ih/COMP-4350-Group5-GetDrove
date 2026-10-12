"""Test helpers: a throwaway signing key and tokens, so services can test protected
endpoints without running Accounts::

    auth = TestAuth()
    app = create_app()
    auth.install(app)
    headers = auth.headers()                      # a valid user
    headers = auth.headers(roles=["user", "admin"])
    token = auth.token(expires_in=-60)            # already expired
"""

import time
import uuid
from typing import TYPE_CHECKING, Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from common_security.config import AUDIENCE, ISSUER, AuthSettings
from common_security.keys import StaticKeys
from common_security.validator import TokenValidator

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestAuth:
    __test__ = False  # not a pytest test class

    def __init__(self, kid: str = "test-key") -> None:
        self.kid = kid
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        self.jwks: dict[str, Any] = {"keys": [{**public, "kid": kid, "alg": "RS256", "use": "sig"}]}
        self.user_id = uuid.uuid4()

    def validator(self) -> TokenValidator:
        return TokenValidator(StaticKeys(self.jwks), AuthSettings())

    def install(self, app: "FastAPI") -> None:
        """Makes the app accept this helper's tokens."""
        app.state.token_validator = self.validator()

    def token(
        self,
        *,
        user_id: uuid.UUID | None = None,
        roles: list[str] | None = None,
        expires_in: int = 900,
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(user_id or self.user_id),
            "roles": roles if roles is not None else ["user"],
            "iat": now,
            "exp": now + expires_in,
            "iss": ISSUER,
            "aud": AUDIENCE,
            **overrides,
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": self.kid})

    def headers(self, **kwargs: Any) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(**kwargs)}"}

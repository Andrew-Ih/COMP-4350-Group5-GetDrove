"""The real ``AccessTokenIssuer``: RS256 JWTs signed with Accounts' key (ADR 0006, #91).

The claims are the ones every service checks with ``common_security``: ``sub`` (user ID),
``roles``, ``iat``, ``exp``, ``iss`` and ``aud``, with ``kid`` in the header naming the key
published at /.well-known/jwks.json. No email or name: other services only get the user ID.
"""

from datetime import datetime, timedelta

import jwt

from accounts.adapters.security.signing_key import ALGORITHM, SigningKey
from accounts.domain.user import User
from common_security.config import AUDIENCE, ISSUER

ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)


class JwtAccessTokenIssuer:
    def __init__(self, signing_key: SigningKey) -> None:
        self._key = signing_key

    @property
    def lifetime(self) -> timedelta:
        return ACCESS_TOKEN_LIFETIME

    def issue(self, user: User, now: datetime) -> str:
        issued_at = int(now.timestamp())
        claims = {
            "sub": str(user.id),
            "roles": user.roles,
            "iat": issued_at,
            "exp": issued_at + int(ACCESS_TOKEN_LIFETIME.total_seconds()),
            "iss": ISSUER,
            "aud": AUDIENCE,
        }
        return jwt.encode(
            claims, self._key.private_key, algorithm=ALGORITHM, headers={"kid": self._key.kid}
        )

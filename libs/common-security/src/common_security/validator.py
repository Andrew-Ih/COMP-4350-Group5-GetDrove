"""Checks an access token and returns who it belongs to."""

from uuid import UUID

import jwt

from common_security.config import AuthSettings
from common_security.errors import InvalidTokenError, TokenExpiredError
from common_security.keys import KeySource
from common_security.user import CurrentUser

ALGORITHM = "RS256"


class TokenValidator:
    def __init__(self, keys: KeySource, settings: AuthSettings | None = None) -> None:
        self._keys = keys
        self._settings = settings or AuthSettings()

    async def validate(self, token: str) -> CurrentUser:
        """Raises ``InvalidTokenError`` or ``TokenExpiredError`` (both 401)."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("The access token is malformed.") from exc

        # Only RS256: never let the token choose a weaker algorithm (or "none").
        if header.get("alg") != ALGORITHM or not isinstance(header.get("kid"), str):
            raise InvalidTokenError("The access token isn't signed the way we expect.")

        key = await self._keys.get_key(header["kid"])
        if key is None:
            raise InvalidTokenError("The access token was signed with an unknown key.")

        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=[ALGORITHM],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                leeway=self._settings.leeway_seconds,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("The access token has expired; refresh it.") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("The access token is invalid.") from exc

        try:
            user_id = UUID(str(claims["sub"]))
        except ValueError as exc:
            raise InvalidTokenError("The access token's subject isn't a user ID.") from exc
        roles = claims.get("roles")
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise InvalidTokenError("The access token has no roles.")
        return CurrentUser(id=user_id, roles=frozenset(roles))

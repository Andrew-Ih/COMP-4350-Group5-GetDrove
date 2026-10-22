"""Refresh tokens: the "stay logged in" pass, kept in an HttpOnly cookie.

Only the SHA-256 hash is saved. Each use swaps it for a new one (#90), and
``replaced_by_id`` records which, so a stolen token being reused can be spotted.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID, uuid4

from accounts.domain.verification import hash_token

REFRESH_TOKEN_LIFETIME = timedelta(days=7)


@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None  # set on logout, or when swapped for a new one
    replaced_by_id: UUID | None = None  # the token that replaced this one

    @classmethod
    def issue(cls, user_id: UUID, now: datetime) -> tuple[Self, str]:
        """A new token, valid for 7 days. Returns it with the token for the cookie, which
        is never saved."""
        token = secrets.token_urlsafe(32)
        return cls(uuid4(), user_id, hash_token(token), now + REFRESH_TOKEN_LIFETIME), token

    def is_active(self, now: datetime) -> bool:
        """Not revoked and not expired."""
        return self.revoked_at is None and now < self.expires_at

    def rotate(self, now: datetime) -> tuple["RefreshToken", str]:
        """Swaps this token for a new one (each refresh). This one stops working and
        records its replacement, so if it's ever presented again, that's a copy being
        reused. Returns the new token and the token for the new cookie."""
        new, cookie_token = RefreshToken.issue(self.user_id, now)
        self.revoked_at = now
        self.replaced_by_id = new.id
        return new, cookie_token

    def revoke(self, now: datetime) -> None:
        """Stops this token working (logout). Already revoked: keeps the first time."""
        if self.revoked_at is None:
            self.revoked_at = now

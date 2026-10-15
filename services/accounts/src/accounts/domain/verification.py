"""Email verification tokens: the secret part of the link in the verification email.

Only the SHA-256 hash is saved, so a leaked database doesn't give anyone working links.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID, uuid4

from accounts.domain.errors import InvalidVerificationTokenError, VerificationTokenExpiredError

TOKEN_LIFETIME = timedelta(hours=24)


def hash_token(token: str) -> str:
    """The SHA-256 hex digest (64 characters) that's saved instead of the token."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class VerificationToken:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None

    @classmethod
    def issue(cls, user_id: UUID, now: datetime) -> tuple[Self, str]:
        """A new token, valid for 24 hours. Returns it with the token for the link, which
        is never saved."""
        token = secrets.token_urlsafe(32)
        return cls(uuid4(), user_id, hash_token(token), now + TOKEN_LIFETIME), token

    def consume(self, now: datetime) -> None:
        """Uses the token up. Already used (or replaced by a resend): 400. Expired: 410.

        "Used" is checked first, so a link that's both used and old says it was used.
        """
        if self.consumed_at is not None:
            raise InvalidVerificationTokenError("This link has already been used.")
        if now >= self.expires_at:
            raise VerificationTokenExpiredError("This link has expired. Request a new one.")
        self.consumed_at = now

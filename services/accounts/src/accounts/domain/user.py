"""A GetDrove account. Every account is a rider and a driver; ``is_admin`` adds "admin"."""

from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from accounts.domain.email import Email


@dataclass
class User:
    id: UUID
    email: Email
    password_hash: str  # Argon2id hash (ADR 0020), never the password itself
    first_name: str
    last_name: str
    email_verified_at: datetime | None = None
    is_admin: bool = False

    @classmethod
    def register(cls, email: Email, password_hash: str, first_name: str, last_name: str) -> Self:
        """A new account: unverified, not an admin."""
        return cls(uuid4(), email, password_hash, first_name, last_name)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def roles(self) -> list[str]:
        """The contract's roles: ["user"], or ["user", "admin"]."""
        return ["user", "admin"] if self.is_admin else ["user"]

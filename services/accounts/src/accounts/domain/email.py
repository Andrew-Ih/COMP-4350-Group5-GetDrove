"""A student's email address: always a lowercase @myumanitoba.ca address."""

from dataclasses import dataclass
from typing import Self

from accounts.domain.errors import EmailNotUofMError
from common_web import InvalidField

UOFM_DOMAIN = "myumanitoba.ca"


@dataclass(frozen=True)
class Email:
    """An email that has already been checked and lowercased.

    Stored lowercase so the unique index on users.email treats Ada@ and ada@ as the same
    account. Create one with ``Email.parse``.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        normalized = raw.strip().lower()
        local, _, domain = normalized.rpartition("@")
        if not local or "@" in local or domain != UOFM_DOMAIN:
            raise EmailNotUofMError(
                "Use your @myumanitoba.ca email.",
                [InvalidField("email", "Must be a @myumanitoba.ca address")],
            )
        return cls(normalized)

    def __str__(self) -> str:
        return self.value

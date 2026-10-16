"""A student's email address: always a lowercase @myumanitoba.ca address."""

import re
from dataclasses import dataclass
from typing import Self

from accounts.domain.errors import EmailNotUofMError
from common_web import InvalidField, InvalidInputError

UOFM_DOMAIN = "myumanitoba.ca"

# The part before the @: letters, digits and . _ % + -, with dots only between other
# characters. Catches typos like "a b@" or ".@" before a verification email is sent.
_LOCAL_PART = re.compile(r"[a-z0-9_%+-]+(\.[a-z0-9_%+-]+)*")


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
        local, at, domain = normalized.rpartition("@")
        if not at or domain != UOFM_DOMAIN:
            raise EmailNotUofMError(
                "Use your @myumanitoba.ca email.",
                [InvalidField("email", "Must be a @myumanitoba.ca address")],
            )
        if not _LOCAL_PART.fullmatch(local):
            raise InvalidInputError(
                "Check your email address for typos.",
                [InvalidField("email", "Enter a valid email address")],
            )
        return cls(normalized)

    def __str__(self) -> str:
        return self.value

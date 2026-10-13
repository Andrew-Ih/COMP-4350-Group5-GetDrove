"""Who is making the request, as proven by their access token."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles

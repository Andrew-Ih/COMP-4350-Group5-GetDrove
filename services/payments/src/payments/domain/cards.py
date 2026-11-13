"""Customer references and safe card display information; never raw card details."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Customer:
    user_id: UUID
    stripe_customer_id: str | None
    default_payment_method_id: str | None = None


@dataclass(frozen=True)
class SavedCard:
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    created: int


@dataclass(frozen=True)
class CardView:
    card: SavedCard
    is_default: bool

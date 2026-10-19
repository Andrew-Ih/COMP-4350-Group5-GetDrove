"""Request and response models for the Payments API (Sprint 1 contract, issue #108)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


class QuoteRequest(ApiModel):
    distance_meters: int = Field(
        ge=0, le=200_000, description="How far the rider travels in the car.", examples=[9300]
    )


class Quote(ApiModel):
    amount_cents: int = Field(
        ge=0,
        description="$0.45 per km, rounded to the nearest 5 cents, at least $2.00.",
        examples=[420],
    )
    currency: Literal["CAD"] = "CAD"
    explanation: str = Field(description="One line for the rider.", examples=["9.3 km at $0.45/km"])


class InvalidFieldOut(ApiModel):
    field: str
    message: str


class Problem(ApiModel):
    """Every error response (RFC 9457 Problem Details, `application/problem+json`)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str = Field(description="Stable error name.")
    request_id: str | None = None
    errors: list[InvalidFieldOut] | None = None

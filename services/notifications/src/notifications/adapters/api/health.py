"""Health check used by Docker, Traefik and the deploy smoke test."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"]
    service: str


@router.get("/health")
async def health() -> HealthOut:
    return HealthOut(status="ok", service="notifications")

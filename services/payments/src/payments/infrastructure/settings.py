"""Configuration from environment variables (prefix ``PAYMENTS_``), with local-dev defaults."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PAYMENTS_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/getdrove"
    rate_cents_per_km: int = Field(default=45, ge=0)
    minimum_fare_cents: int = Field(default=200, ge=0)


def get_settings() -> Settings:
    return Settings()

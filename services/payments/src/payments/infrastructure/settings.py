"""Configuration from environment variables (prefix ``PAYMENTS_``), with local-dev defaults."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PAYMENTS_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/getdrove"
    rate_cents_per_km: int = Field(default=45, ge=0)
    minimum_fare_cents: int = Field(default=200, ge=0)

    stripe_secret_key: SecretStr | None = None
    stripe_api_base: str = "https://api.stripe.com"

    @field_validator("stripe_secret_key")
    @classmethod
    def require_test_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith("sk_test_"):
            raise ValueError("Only Stripe test secret keys (sk_test_) are supported")
        return value


def get_settings() -> Settings:
    return Settings()

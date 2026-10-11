"""Configuration from environment variables (prefix ``PAYMENTS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAYMENTS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/getdrove"


def get_settings() -> Settings:
    return Settings()

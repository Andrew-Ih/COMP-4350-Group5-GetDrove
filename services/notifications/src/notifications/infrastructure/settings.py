"""Configuration from environment variables (prefix ``NOTIFICATIONS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFICATIONS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://notifications:notifications@localhost:5432/getdrove"


def get_settings() -> Settings:
    return Settings()

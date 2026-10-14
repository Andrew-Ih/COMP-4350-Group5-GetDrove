"""Configuration from environment variables (prefix ``TRIPS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIPS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://trips:trips@localhost:5432/getdrove"


def get_settings() -> Settings:
    return Settings()

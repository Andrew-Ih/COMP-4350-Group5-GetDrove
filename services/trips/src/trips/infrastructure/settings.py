"""Configuration from environment variables (prefix ``TRIPS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIPS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://trips:trips@localhost:5432/getdrove"
    routing_url: str = "http://localhost:8003"
    payments_url: str = "http://localhost:8004"
    redis_url: str = "redis://localhost:6379/0"


def get_settings() -> Settings:
    return Settings()

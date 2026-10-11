"""Configuration from environment variables (prefix ``ROUTING_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROUTING_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://routing:routing@localhost:5432/getdrove"


def get_settings() -> Settings:
    return Settings()

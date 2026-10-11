"""Configuration from environment variables (prefix ``ACCOUNTS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ACCOUNTS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://accounts:accounts@localhost:5432/getdrove"


def get_settings() -> Settings:
    return Settings()

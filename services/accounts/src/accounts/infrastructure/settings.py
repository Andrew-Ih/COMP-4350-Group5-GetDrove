"""Configuration from environment variables (prefix ``ACCOUNTS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ACCOUNTS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://accounts:accounts@localhost:5432/getdrove"
    # "production" on the live server; anything else is local development.
    environment: str = "development"
    # PEM-encoded RSA private key for signing access tokens. Required in production
    # (from GitHub Secrets); locally a temporary key is generated if it's missing.
    jwt_private_key: str | None = None


def get_settings() -> Settings:
    return Settings()

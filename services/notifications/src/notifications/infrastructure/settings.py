"""Configuration from environment variables (prefix ``NOTIFICATIONS_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFICATIONS_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://notifications:notifications@localhost:5432/getdrove"
    # Where events are read from (the events.accounts stream).
    redis_url: str = "redis://localhost:6379/0"

    # Email (ADR 0010). Defaults point at Mailpit from Docker Compose, which catches every
    # email. Production uses Brevo's SMTP relay with STARTTLS and a login.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    email_from: str = "GetDrove <no-reply@getdrove.local>"

    # The web app's address, for links in emails: the Next.js dev server locally, the live
    # site in production. Never hard-coded, so links always open the right site.
    web_base_url: str = "http://localhost:3000"


def get_settings() -> Settings:
    return Settings()

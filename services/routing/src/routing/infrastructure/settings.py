"""Configuration from environment variables (prefix ``ROUTING_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROUTING_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://routing:routing@localhost:5432/getdrove"
    # OSRM (ADR 0008, infra/osrm/README.md): driving routes, and walking times to pickups.
    # Defaults are the ports Docker Compose publishes; inside Docker they're osrm-car/-foot.
    osrm_car_url: str = "http://localhost:5050"
    osrm_foot_url: str = "http://localhost:5051"


def get_settings() -> Settings:
    return Settings()

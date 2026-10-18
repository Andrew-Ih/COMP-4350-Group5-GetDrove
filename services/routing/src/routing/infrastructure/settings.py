"""Configuration from environment variables (prefix ``ROUTING_``), with local-dev defaults."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROUTING_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://routing:routing@localhost:5432/getdrove"
    # OSRM (ADR 0008, infra/osrm/README.md): driving routes, and walking times to pickups.
    # Defaults are the ports Docker Compose publishes; inside Docker they're osrm-car/-foot.
    osrm_car_url: str = "http://localhost:5050"
    osrm_foot_url: str = "http://localhost:5051"
    # Computing a route must take under 3 seconds (contract), and Trips gives up after 5.
    osrm_timeout_seconds: float = 2.5
    # Riders within this straight-line distance of a route are checked by walking time (#25,
    # #26). Generous on purpose: the walking check is what rules riders out.
    corridor_meters: int = 800
    # A trip matches if the rider can walk to its route within this (#26). OSRM's foot profile
    # walks at 5 km/h, so 10 minutes is about 830 m: just over the corridor.
    max_walk_seconds: int = 600


def get_settings() -> Settings:
    return Settings()

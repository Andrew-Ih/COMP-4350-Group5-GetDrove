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
    # Trips waits for a detour while the rider's request is open, and the contract says to fail
    # fast with 503 when OSRM is slow (#36): under 1 second.
    detour_timeout_seconds: float = 0.8
    # Riders within this straight-line distance of a route are checked by walking time (#25,
    # #26). Generous on purpose: the walking check is what rules riders out.
    corridor_meters: int = 800
    # A trip matches if the rider can walk to its route within this (#26). OSRM's foot profile
    # walks at 5 km/h, so 10 minutes is about 830 m: just over the corridor.
    max_walk_seconds: int = 600
    # Redis: the detour plan cache and the events Routing consumes (#37).
    redis_url: str = "redis://localhost:6379/0"
    # A plan is worked out for exact points, so it is never wrong, only unused: the TTL just
    # frees memory.
    detour_plan_ttl_seconds: int = 3600
    # The cache must never eat the 1 s detour budget: a slow Redis counts as a miss. Redis
    # answers in about a millisecond, so this plus detour_timeout_seconds stays under 1 s.
    plan_cache_timeout_seconds: float = 0.1


def get_settings() -> Settings:
    return Settings()

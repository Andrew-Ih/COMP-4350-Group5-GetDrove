"""The detour plan cache in Redis (#37).

Each plan is stored under the trip and a hash of the exact points it was worked out for, so
it can never be used for other points. The keys of each trip are also listed in a set, so
the events that change a trip's pickups can drop them all at once. A Redis failure is a
miss, never an error: a quote doesn't need the cache.
"""

import json
import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _plan(value: Any) -> list[list[float]] | None:
    """The stored value as a square matrix of numbers, or None if it isn't one."""
    if not isinstance(value, list) or not value:
        return None
    size = len(value)
    for row in value:
        if not isinstance(row, list) or len(row) != size:
            return None
        if any(isinstance(n, bool) or not isinstance(n, int | float) for n in row):
            return None
    return [[float(n) for n in row] for row in value]


class RedisDetourPlans:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        # redis-py's async command types are too loose for mypy --strict to check usefully.
        self._redis: Any = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _entry(trip_id: UUID, key: str) -> str:
        return f"routing:detour:{trip_id}:{key}"

    @staticmethod
    def _index(trip_id: UUID) -> str:
        return f"routing:detour:{trip_id}:keys"

    async def get(self, trip_id: UUID, key: str) -> list[list[float]] | None:
        try:
            raw = await self._redis.get(self._entry(trip_id, key))
        except RedisError:
            logger.warning("Detour plan cache unavailable; recomputing", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            return _plan(json.loads(raw))
        except ValueError:
            return None

    async def put(self, trip_id: UUID, key: str, matrix: list[list[float]]) -> None:
        entry = self._entry(trip_id, key)
        index = self._index(trip_id)
        try:
            await self._redis.set(entry, json.dumps(matrix), ex=self._ttl)
            await self._redis.sadd(index, entry)
            await self._redis.expire(index, self._ttl)
        except RedisError:
            logger.warning("Could not save a detour plan", exc_info=True)

    async def forget(self, trip_id: UUID) -> None:
        index = self._index(trip_id)
        try:
            entries = await self._redis.smembers(index)
            await self._redis.delete(*entries, index)
        except RedisError:
            logger.warning("Could not drop the detour plans of trip %s", trip_id, exc_info=True)

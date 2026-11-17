"""The Redis detour plan cache, against an in-memory Redis (#37)."""

from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from routing.adapters.redis_plans import RedisDetourPlans

TRIP, OTHER = uuid4(), uuid4()
PLAN = [[0.0, 60.0], [60.0, 0.0]]


class FakeRedis:
    """The few commands the cache uses. Redis returns bytes, so this does too."""

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.sets: dict[str, set[bytes]] = {}
        self.down = False
        self.calls = 0

    def _check(self) -> None:
        self.calls += 1
        if self.down:
            raise RedisError("Redis is down")

    async def get(self, key: str) -> bytes | None:
        self._check()
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._check()
        self.values[key] = value.encode()

    async def sadd(self, key: str, *members: str) -> None:
        self._check()
        self.sets.setdefault(key, set()).update(m.encode() for m in members)

    async def expire(self, key: str, seconds: int) -> None:
        self._check()

    async def smembers(self, key: str) -> "set[bytes]":
        self._check()
        return set(self.sets.get(key, set()))

    async def delete(self, *keys: str | bytes) -> None:
        self._check()
        for key in keys:
            text = key.decode() if isinstance(key, bytes) else key
            self.values.pop(text, None)
            self.sets.pop(text, None)


def cache(redis: FakeRedis) -> RedisDetourPlans:
    return RedisDetourPlans(redis, ttl_seconds=60)  # type: ignore[arg-type]


async def test_a_saved_plan_comes_back() -> None:
    plans = cache(FakeRedis())
    await plans.put(TRIP, "k1", PLAN)

    assert await plans.get(TRIP, "k1") == PLAN
    assert await plans.get(TRIP, "other-key") is None
    assert await plans.get(OTHER, "k1") is None


async def test_forgetting_a_trip_drops_only_its_plans() -> None:
    plans = cache(FakeRedis())
    await plans.put(TRIP, "k1", PLAN)
    await plans.put(TRIP, "k2", PLAN)
    await plans.put(OTHER, "k1", PLAN)

    await plans.forget(TRIP)

    assert await plans.get(TRIP, "k1") is None
    assert await plans.get(TRIP, "k2") is None
    assert await plans.get(OTHER, "k1") == PLAN


async def test_forgetting_a_trip_with_no_plans_is_fine() -> None:
    await cache(FakeRedis()).forget(uuid4())


async def test_redis_down_is_a_miss_not_an_error() -> None:
    redis = FakeRedis()
    plans = cache(redis)
    await plans.put(TRIP, "k1", PLAN)
    redis.down = True

    assert await plans.get(TRIP, "k1") is None
    await plans.put(TRIP, "k2", PLAN)
    await plans.forget(TRIP)


@pytest.mark.parametrize(
    "stored", [b"not json", b"[]", b"[[0, 1]]", b'[["a"]]', b"{}", b"[[true]]"]
)
async def test_something_that_is_not_a_plan_is_a_miss(stored: bytes) -> None:
    redis = FakeRedis()
    redis.values[f"routing:detour:{TRIP}:k1"] = stored

    assert await cache(redis).get(TRIP, "k1") is None


async def test_after_a_failure_redis_is_left_alone_for_a_few_seconds() -> None:
    now = [100.0]
    redis = FakeRedis()
    plans = RedisDetourPlans(redis, ttl_seconds=60, clock=lambda: now[0])  # type: ignore[arg-type]
    redis.down = True

    assert await plans.get(TRIP, "k1") is None
    asked = redis.calls

    await plans.put(TRIP, "k1", PLAN)  # skipped
    assert await plans.get(TRIP, "k1") is None  # skipped
    assert redis.calls == asked

    redis.down = False
    now[0] += 6  # past the back-off
    await plans.put(TRIP, "k1", PLAN)
    assert await plans.get(TRIP, "k1") == PLAN

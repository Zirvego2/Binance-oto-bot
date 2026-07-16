"""Redis tabanli dagitik kilit (worker + API manuel islem)."""

from __future__ import annotations

import uuid

from redis.asyncio import Redis

_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LockNotAcquiredError(Exception):
    pass


class DistributedLock:
    def __init__(self, redis: Redis, name: str, ttl_seconds: int = 30) -> None:
        self._redis = redis
        self._key = f"lock:{name}"
        self._name = name
        self._ttl_seconds = ttl_seconds
        self._token = uuid.uuid4().hex

    async def acquire(self, blocking_timeout_seconds: float = 5.0) -> bool:
        import asyncio

        loop = asyncio.get_event_loop()
        deadline = loop.time() + blocking_timeout_seconds
        while True:
            acquired = await self._redis.set(self._key, self._token, nx=True, ex=self._ttl_seconds)
            if acquired:
                return True
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(0.2)

    async def release(self) -> None:
        await self._redis.eval(_RELEASE_SCRIPT, 1, self._key, self._token)

    async def extend(self) -> None:
        await self._redis.expire(self._key, self._ttl_seconds)

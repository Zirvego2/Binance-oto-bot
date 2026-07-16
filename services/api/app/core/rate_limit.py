"""Basit sabit-pencere Redis tabanli rate limiter (sartname bolum 22 & 28)."""

from __future__ import annotations

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded, retry after {retry_after_seconds}s")


async def enforce_rate_limit(
    redis: Redis, key: str, max_requests: int, window_seconds: int
) -> None:
    """``key`` icin sabit pencere sayaci uygular. Asilirsa RateLimitExceeded firlatir."""

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > max_requests:
        ttl = await redis.ttl(key)
        raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))

"""Redis tabanli cache — rejim, korelasyon, GPT sonuclari."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis


async def cache_get(redis: Redis | None, key: str) -> Any | None:
    if redis is None:
        return None
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cache_set(redis: Redis | None, key: str, value: Any, ttl_seconds: int = 60) -> None:
    if redis is None:
        return
    payload = json.dumps(value, default=str)
    await redis.setex(key, ttl_seconds, payload)


def regime_cache_key(scope: str, timeframe: str) -> str:
    return f"enhanced:regime:{scope}:{timeframe}"


def correlation_cache_key(symbol: str, lookback: int) -> str:
    return f"enhanced:corr:{symbol}:{lookback}"


def ai_explanation_cache_key(signal_id: str) -> str:
    return f"enhanced:ai_explanation:{signal_id}"

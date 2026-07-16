"""Redis tabanli dagitik kilit (sartname bolum 24)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import WorkerLock
from shared.distributed_lock import DistributedLock, LockNotAcquiredError

__all__ = ["DistributedLock", "LockNotAcquiredError", "distributed_lock"]


@asynccontextmanager
async def distributed_lock(
    redis: Redis, session: AsyncSession, name: str, holder_id: str, ttl_seconds: int = 30
):
    """Kritik bolgeyi korur; ayni zamanda denetim icin WorkerLock kaydi tutar."""

    lock = DistributedLock(redis, name, ttl_seconds=ttl_seconds)
    acquired = await lock.acquire()
    if not acquired:
        raise LockNotAcquiredError(f"'{name}' kilidi alinamadi (baska bir worker calisiyor olabilir)")

    now = datetime.now(timezone.utc)
    lock_row = WorkerLock(
        lock_name=name,
        holder_id=holder_id,
        acquired_at=now,
        expires_at=now,
    )
    session.add(lock_row)
    await session.flush()
    try:
        yield lock
    finally:
        lock_row.released_at = datetime.now(timezone.utc)
        await lock.release()

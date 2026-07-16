"""Worker BTC impuls otomatik dongusu (musteri bazli)."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings
from shared.distributed_lock import DistributedLock
from shared.impulse.executor import execute_impulse_candidates, scan_impulse

from .order_engine import PositionOpenSkipped, open_position_for_signal

logger = logging.getLogger("worker.impulse")


async def impulse_auto_cycle(
    session: AsyncSession,
    adapter,
    settings_row: BotSettings,
    bot_mode: str,
    lock: DistributedLock,
    redis: Redis,
) -> None:
    if settings_row.impulse_mode != "AUTO":
        return
    if settings_row.mode != bot_mode:
        return

    scan_result = await scan_impulse(session, adapter, settings_row)
    if not scan_result.candidates or scan_result.cooldown_active:
        return

    acquired = await lock.acquire(blocking_timeout_seconds=2.0)
    if not acquired:
        return

    try:
        exec_result = await execute_impulse_candidates(
            session,
            adapter,
            settings_row,
            scan_result.candidates,
            open_position_fn=open_position_for_signal,
            position_open_skipped=PositionOpenSkipped,
            triggered_by="auto",
        )
        if exec_result.opened:
            logger.info(
                "Impuls AUTO (admin=%s): %s pozisyon acildi (BTC %%%.2f %s)",
                settings_row.admin_id,
                len(exec_result.opened),
                exec_result.btc_change_pct,
                exec_result.btc_direction,
            )
    finally:
        await lock.release()

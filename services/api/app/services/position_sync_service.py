"""Borsa ile yerel pozisyon kayitlarini senkronize eder (musteri bazli)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Position

from ..core.binance_client import get_binance_adapter_for_admin
from ..core.worker_bridge import ensure_worker_import_path
from .settings_service import get_or_create_bot_settings

logger = logging.getLogger("api.position_sync")

_last_light_sync: dict[str, float] = {}
_last_full_sync: dict[str, float] = {}
_MIN_LIGHT_SYNC_SEC = 3.0
_MIN_FULL_SYNC_SEC = 15.0


@dataclass(frozen=True, slots=True)
class PositionSyncResult:
    local_open_count: int
    exchange_open_count: int
    closed_ghosts: list[str]
    synced_at: str
    skipped_throttle: bool = False


async def _count_local_open(session: AsyncSession, bot_mode: str, admin_id: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == bot_mode,
            Position.admin_id == admin_id,
        )
    )
    return int(result.scalar_one())


async def sync_positions_from_exchange(
    session: AsyncSession,
    admin_id: str,
    bot_mode: str,
    *,
    force: bool = False,
    full: bool = False,
) -> PositionSyncResult:
    from datetime import datetime, timezone

    now_mono = time.monotonic()
    throttle_key = f"{admin_id}:{bot_mode}:{'full' if full else 'light'}"
    last_sync = _last_full_sync if full else _last_light_sync
    min_interval = _MIN_FULL_SYNC_SEC if full else _MIN_LIGHT_SYNC_SEC

    if not force and now_mono - last_sync.get(throttle_key, 0.0) < min_interval:
        local_count = await _count_local_open(session, bot_mode, admin_id)
        return PositionSyncResult(
            local_open_count=local_count,
            exchange_open_count=local_count,
            closed_ghosts=[],
            synced_at=datetime.now(timezone.utc).isoformat(),
            skipped_throttle=True,
        )

    if bot_mode == "paper":
        local_count = await _count_local_open(session, bot_mode, admin_id)
        return PositionSyncResult(
            local_open_count=local_count,
            exchange_open_count=local_count,
            closed_ghosts=[],
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    ensure_worker_import_path()
    if full:
        from worker.position_monitor import refresh_open_positions  # noqa: PLC0415

        sync_fn = refresh_open_positions
    else:
        from worker.position_monitor import reconcile_positions_from_exchange  # noqa: PLC0415

        sync_fn = reconcile_positions_from_exchange

    adapter = await get_binance_adapter_for_admin(session, admin_id, bot_mode)
    try:
        if full:
            await sync_fn(session, adapter, bot_mode, admin_id)
            exchange_positions = await adapter.get_open_positions()
            closed_ghosts: list[str] = []
            local_count = await _count_local_open(session, bot_mode, admin_id)
            exchange_count = len(exchange_positions)
        else:
            closed_ghosts, exchange_count = await sync_fn(session, adapter, bot_mode, admin_id)
            local_count = await _count_local_open(session, bot_mode, admin_id)
    except Exception:  # noqa: BLE001
        logger.exception("Pozisyon senkronizasyonu basarisiz (admin=%s)", admin_id)
        raise

    last_sync[throttle_key] = now_mono

    return PositionSyncResult(
        local_open_count=local_count,
        exchange_open_count=exchange_count,
        closed_ghosts=closed_ghosts,
        synced_at=datetime.now(timezone.utc).isoformat(),
    )


async def sync_positions_if_live_open(session: AsyncSession, admin_id: str) -> PositionSyncResult | None:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    if settings_row.mode == "paper":
        return None
    return await sync_positions_from_exchange(session, admin_id, settings_row.mode)

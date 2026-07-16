"""BTC impuls islem API servisi (musteri bazli)."""

from __future__ import annotations

from typing import Any

from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotEvent, BotRuntimeStatus
from shared.distributed_lock import DistributedLock, LockNotAcquiredError
from shared.impulse.executor import execute_impulse_candidates, scan_impulse
from shared.tenant_settings import get_or_create_bot_runtime

from ..core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin
from ..core.worker_bridge import get_order_engine_module
from .audit_service import record_audit_log
from .settings_service import get_or_create_bot_settings, sync_bot_settings_to_firebase


async def get_impulse_settings(session: AsyncSession, admin_id: str) -> dict[str, Any]:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    runtime = await get_or_create_bot_runtime(session, admin_id)

    data = {
        c.name: getattr(settings_row, c.name)
        for c in settings_row.__table__.columns
        if c.name.startswith("impulse_")
    }
    for field in ("impulse_last_event_at", "impulse_last_scan_at"):
        val = getattr(runtime, field, None)
        data[field] = val.isoformat() if val is not None else None
    data["impulse_last_direction"] = runtime.impulse_last_direction
    data["impulse_last_btc_change_pct"] = runtime.impulse_last_btc_change_pct
    data["impulse_last_opened_count"] = runtime.impulse_last_opened_count or 0
    return data


async def update_impulse_settings(
    session: AsyncSession,
    admin_id: str,
    updates: dict[str, Any],
    ip_address: str | None,
):
    settings_row = await get_or_create_bot_settings(session, admin_id)
    before = {k: str(getattr(settings_row, k)) for k in updates if hasattr(settings_row, k)}

    for key, value in updates.items():
        if value is not None and hasattr(settings_row, key):
            setattr(settings_row, key, value)

    settings_row.updated_by_admin_id = admin_id
    await session.commit()
    await session.refresh(settings_row)

    await record_audit_log(
        session,
        admin_id=admin_id,
        action="IMPULSE_SETTINGS_UPDATE",
        entity_type="bot_settings",
        entity_id=settings_row.id,
        before_data=before,
        after_data={k: str(getattr(settings_row, k)) for k in updates if hasattr(settings_row, k)},
        ip_address=ip_address,
    )
    await sync_bot_settings_to_firebase(session, admin_id, settings_row)
    return settings_row


async def run_impulse_scan(
    session: AsyncSession,
    admin_id: str,
    *,
    manual_side: str | None = None,
) -> Any:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    if not await is_binance_configured_for_admin(session, admin_id, settings_row.mode):
        raise ValueError("Binance baglantisi yapilandirilmamis")

    adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
    return await scan_impulse(
        session,
        adapter,
        settings_row,
        manual_side=manual_side,
        ignore_cooldown=manual_side is not None,
    )


async def run_impulse_execute(
    session: AsyncSession,
    redis: Redis,
    admin_id: str,
    *,
    manual_side: str | None = None,
    symbols: list[str] | None = None,
    max_entries: int | None = None,
    ip_address: str | None = None,
) -> Any:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    if not await is_binance_configured_for_admin(session, admin_id, settings_row.mode):
        raise ValueError("Binance baglantisi yapilandirilmamis")

    adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
    scan_result = await scan_impulse(
        session,
        adapter,
        settings_row,
        manual_side=manual_side,
        ignore_cooldown=True,
    )

    candidates = scan_result.candidates
    if symbols:
        symbol_set = {s.upper() for s in symbols}
        candidates = [c for c in candidates if c.symbol in symbol_set]

    if not candidates:
        return {
            "opened": [],
            "skipped": [],
            "failed": [],
            "btc_direction": scan_result.btc_direction,
            "btc_change_pct": scan_result.btc_change_pct,
            "message": "Acilacak aday bulunamadi",
        }

    order_engine = get_order_engine_module()
    lock = DistributedLock(redis, f"trading_engine:{admin_id}", ttl_seconds=30)
    acquired = await lock.acquire(blocking_timeout_seconds=10.0)
    if not acquired:
        raise LockNotAcquiredError("Islem kilidi alinamadi")

    try:
        result = await execute_impulse_candidates(
            session,
            adapter,
            settings_row,
            candidates,
            open_position_fn=order_engine.open_position_for_signal,
            position_open_skipped=order_engine.PositionOpenSkipped,
            triggered_by="manual",
            max_entries=max_entries,
        )
    finally:
        await lock.release()

    await record_audit_log(
        session,
        admin_id=admin_id,
        action="IMPULSE_EXECUTE",
        entity_type="bot_settings",
        entity_id=settings_row.id,
        after_data={
            "opened": result.opened,
            "skipped": result.skipped,
            "failed": result.failed,
        },
        ip_address=ip_address,
    )

    msg = f"{len(result.opened)} pozisyon acildi"
    return {**result.__dict__, "message": msg}


async def list_recent_impulse_events(session: AsyncSession, admin_id: str, limit: int = 20) -> list[BotEvent]:
    result = await session.execute(
        select(BotEvent)
        .where(
            BotEvent.event_type.in_(["IMPULSE_EXECUTE", "IMPULSE_SCAN"]),
            BotEvent.admin_id == admin_id,
        )
        .order_by(desc(BotEvent.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())

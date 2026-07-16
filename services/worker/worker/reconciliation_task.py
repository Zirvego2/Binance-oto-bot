"""Baslangicta ve periyodik olarak calisan reconciliation gorevi (musteri bazli)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.db import BotRuntimeStatus, Position, ReconciliationRun
from shared.reconciliation import LocalPositionSnapshot, reconcile
from shared.reconciliation_policy import SAFE_MODE_MISMATCH_TYPES, critical_mismatches_for_safe_mode
from shared.tenant_settings import get_or_create_bot_runtime

logger = logging.getLogger("worker.reconciliation")

CRITICAL_TYPES = SAFE_MODE_MISMATCH_TYPES  # geriye uyumluluk


async def _heal_ghost_positions_before_reconcile(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    bot_mode: str,
    admin_id: str,
) -> list[str]:
    """DB'de OPEN ama Binance'de olmayan pozisyonlari kapatir."""
    from .position_monitor import reconcile_positions_from_exchange

    try:
        closed_ghosts, _ = await reconcile_positions_from_exchange(session, adapter, bot_mode, admin_id)
    except Exception:  # noqa: BLE001
        logger.exception("Hayalet pozisyon temizligi basarisiz (admin=%s)", admin_id)
        return []
    if closed_ghosts:
        logger.info("Reconciliation oncesi hayalet pozisyonlar kapatildi (admin=%s): %s", admin_id, closed_ghosts)
    return closed_ghosts


async def run_reconciliation(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    bot_mode: str,
    admin_id: str,
    triggered_by: str,
) -> ReconciliationRun:
    await _heal_ghost_positions_before_reconcile(session, adapter, bot_mode, admin_id)

    exchange_positions = await adapter.get_open_positions()
    exchange_algo_orders = await adapter.get_open_algo_orders()

    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == bot_mode,
            Position.admin_id == admin_id,
        )
    )
    local_rows = result.scalars().all()
    local_snapshots = [
        LocalPositionSnapshot(
            position_id=p.id,
            symbol=p.symbol,
            side=p.side,
            quantity=p.quantity,
            entry_price=p.entry_price,
            has_stop_loss=p.stop_loss_algo_order_id is not None,
            has_take_profit=p.take_profit_algo_order_id is not None,
        )
        for p in local_rows
    ]

    report = reconcile(exchange_positions, local_snapshots, exchange_algo_orders)
    now = datetime.now(timezone.utc)
    status_value = (
        "OK"
        if report.is_consistent
        else ("EXTERNAL_POSITION_FOUND" if report.external_positions else "MISMATCH_FOUND")
    )

    run = ReconciliationRun(
        triggered_by=triggered_by,
        status=status_value,
        mismatches_found=len(report.mismatches),
        external_positions_found=len(report.external_positions),
        details={
            "admin_id": admin_id,
            "mismatches": [m.details for m in report.mismatches],
            "external_positions": report.external_positions,
            "missing_on_exchange": report.missing_on_exchange,
            "positions_missing_protection": report.positions_missing_protection,
        },
        entered_safe_mode=False,
        ran_at=now,
    )
    session.add(run)

    runtime = await get_or_create_bot_runtime(session, admin_id)
    critical_mismatches = critical_mismatches_for_safe_mode(report.mismatches)

    if report.missing_on_exchange:
        logger.warning(
            "Binance'de bulunmayan DB pozisyonlari (admin=%s, otomatik temizlik denendi): %s",
            admin_id,
            report.missing_on_exchange,
        )

    if critical_mismatches:
        runtime.run_state = "SAFE_MODE"
        runtime.safe_mode_reason = (
            f"Reconciliation tutarsizligi: {len(critical_mismatches)} kritik uyusmazlik, "
            f"{len(report.external_positions)} harici pozisyon. Admin onayi gerekiyor."
        )
        run.entered_safe_mode = True
        logger.warning("Kritik reconciliation (admin=%s): %s", admin_id, critical_mismatches)
    else:
        if report.positions_missing_protection:
            logger.warning(
                "Korumasi eksik pozisyonlar admin=%s (SAFE_MODE tetiklenmedi): %s",
                admin_id,
                report.positions_missing_protection,
            )
        if runtime.run_state == "SAFE_MODE" and runtime.safe_mode_reason and "Reconciliation" in runtime.safe_mode_reason:
            runtime.run_state = "RUNNING"
            runtime.safe_mode_reason = None
            logger.info("Reconciliation basarili, admin=%s RUNNING", admin_id)

    await session.commit()
    await session.refresh(run)
    return run

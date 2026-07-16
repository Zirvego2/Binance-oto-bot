"""Reconciliation calistirma ve sonucu kaydetme servisi (musteri bazli)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Position, ReconciliationRun
from shared.reconciliation import LocalPositionSnapshot, reconcile
from shared.reconciliation_policy import critical_mismatches_for_safe_mode
from shared.tenant_settings import get_or_create_bot_runtime

from ..core.binance_client import get_binance_adapter_for_admin
from ..core.worker_bridge import ensure_worker_import_path


async def _heal_ghost_positions_before_reconcile(
    session: AsyncSession,
    admin_id: str,
    environment: str,
) -> list[str]:
    if environment == "paper":
        return []
    ensure_worker_import_path()
    from worker.position_monitor import reconcile_positions_from_exchange  # noqa: PLC0415

    adapter = await get_binance_adapter_for_admin(session, admin_id, environment)
    try:
        closed_ghosts, _ = await reconcile_positions_from_exchange(session, adapter, environment, admin_id)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("api.reconciliation").exception(
            "Hayalet pozisyon temizligi basarisiz (admin=%s)", admin_id
        )
        return []
    return closed_ghosts


async def run_and_persist_reconciliation(
    session: AsyncSession,
    admin_id: str,
    environment: str,
    triggered_by: str,
) -> ReconciliationRun:
    adapter = await get_binance_adapter_for_admin(session, admin_id, environment)
    closed_ghosts = await _heal_ghost_positions_before_reconcile(session, admin_id, environment)
    if closed_ghosts:
        import logging

        logging.getLogger("api.reconciliation").info(
            "Reconciliation oncesi hayalet pozisyonlar kapatildi (admin=%s): %s", admin_id, closed_ghosts
        )

    exchange_positions = await adapter.get_open_positions()
    exchange_algo_orders = await adapter.get_open_algo_orders()

    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == environment,
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

    if critical_mismatches:
        runtime.run_state = "SAFE_MODE"
        runtime.safe_mode_reason = (
            f"Reconciliation tutarsizligi: {len(critical_mismatches)} kritik uyusmazlik, "
            f"{len(report.external_positions)} harici pozisyon. Admin onayi gerekiyor."
        )
        run.entered_safe_mode = True
    elif runtime.run_state == "SAFE_MODE" and runtime.safe_mode_reason and "Reconciliation" in runtime.safe_mode_reason:
        runtime.run_state = "RUNNING"
        runtime.safe_mode_reason = None

    await session.commit()
    await session.refresh(run)
    return run

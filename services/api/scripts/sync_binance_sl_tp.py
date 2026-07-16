#!/usr/bin/env python3
"""Binance acik pozisyonlari DB ile esitler ve bot ayarlarina gore SL/TP gunceller.

Kullanim (sunucuda):
    docker compose exec api python scripts/sync_binance_sl_tp.py admin@example.com
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.binance_client import get_binance_adapter_for_admin
from app.core.database import AsyncSessionLocal
from app.core.worker_bridge import ensure_worker_import_path
from app.services.reconciliation_service import run_and_persist_reconciliation
from app.services.settings_service import get_or_create_bot_settings
from shared.db import Admin, BotRuntimeStatus, Position, Symbol
from shared.db.base import new_uuid
from shared.enums import PositionSide
from shared.roi import compute_roi_from_prices

ensure_worker_import_path()
from worker.order_engine import refresh_position_protective_orders  # noqa: E402


async def _sync_position_from_exchange(position: Position, exch) -> None:
    if exch.quantity and exch.quantity > 0:
        position.quantity = abs(exch.quantity)
    if exch.entry_price and exch.entry_price > 0:
        position.entry_price = exch.entry_price
        position.notional_usdt = exch.entry_price * position.quantity
    position.mark_price = exch.mark_price
    position.unrealized_pnl = exch.unrealized_pnl
    position.liquidation_price = exch.liquidation_price or position.liquidation_price
    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    position.roi_pct = compute_roi_from_prices(
        position.entry_price,
        exch.mark_price,
        position.quantity,
        Decimal(position.leverage),
        side_enum,
    )


async def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"

    async with AsyncSessionLocal() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == email.lower()))).scalar_one_or_none()
        if admin is None:
            raise SystemExit(f"Kullanici bulunamadi: {email}")

        settings = await get_or_create_bot_settings(session, admin.id)
        if settings.mode == "paper":
            raise SystemExit("PAPER modunda calistirilamaz.")

        adapter = await get_binance_adapter_for_admin(session, admin.id, settings.mode)
        exchange_positions = await adapter.get_open_positions()
        exchange_by_symbol = {p.symbol: p for p in exchange_positions}

        local_rows = (
            await session.execute(
                select(Position).where(
                    Position.status == "OPEN",
                    Position.bot_mode == settings.mode,
                    Position.admin_id == admin.id,
                )
            )
        ).scalars().all()
        local_symbols = {p.symbol for p in local_rows}

        imported: list[str] = []
        now = datetime.now(timezone.utc)

        for exch in exchange_positions:
            if exch.symbol in local_symbols:
                continue
            side = "LONG" if exch.quantity > 0 else "SHORT"
            qty = abs(exch.quantity)
            margin = exch.isolated_margin if exch.isolated_margin and exch.isolated_margin > 0 else (
                qty * exch.entry_price / Decimal(max(exch.leverage, 1))
            )
            side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
            roi = compute_roi_from_prices(
                exch.entry_price, exch.mark_price, qty, Decimal(exch.leverage), side_enum
            )
            session.add(
                Position(
                    id=new_uuid(),
                    admin_id=admin.id,
                    symbol=exch.symbol,
                    side=side,
                    binance_position_side=exch.position_side or "BOTH",
                    status="OPEN",
                    bot_mode=settings.mode,
                    is_external=True,
                    margin_type=exch.margin_type or "ISOLATED",
                    leverage=int(exch.leverage or 1),
                    margin_usdt=margin,
                    quantity=qty,
                    notional_usdt=qty * exch.entry_price,
                    entry_price=exch.entry_price,
                    mark_price=exch.mark_price,
                    liquidation_price=exch.liquidation_price or None,
                    unrealized_pnl=exch.unrealized_pnl,
                    roi_pct=roi,
                    open_reason="EXTERNAL",
                    opened_at=now,
                    protective_orders_ok=False,
                )
            )
            imported.append(exch.symbol)

        if imported:
            await session.commit()
            print(f"Ice aktarilan harici pozisyon ({len(imported)}): {', '.join(imported)}")
        else:
            print("Yeni harici pozisyon yok.")

        local_rows = (
            await session.execute(
                select(Position).where(
                    Position.status == "OPEN",
                    Position.bot_mode == settings.mode,
                    Position.admin_id == admin.id,
                )
            )
        ).scalars().all()

        sl_tp_ok: list[str] = []
        sl_tp_fail: list[str] = []

        for position in local_rows:
            exch = exchange_by_symbol.get(position.symbol)
            if exch is not None:
                await _sync_position_from_exchange(position, exch)

            symbol_row = (
                await session.execute(select(Symbol).where(Symbol.symbol == position.symbol))
            ).scalar_one_or_none()
            if symbol_row is None:
                sl_tp_fail.append(f"{position.symbol}(symbol kaydi yok)")
                continue

            ok = await refresh_position_protective_orders(
                session, adapter, settings, position, symbol_row
            )
            if ok:
                sl_tp_ok.append(position.symbol)
            else:
                sl_tp_fail.append(position.symbol)

        await session.commit()

        print(f"\nSL/TP guncellendi ({len(sl_tp_ok)}): {', '.join(sl_tp_ok) or '-'}")
        if sl_tp_fail:
            print(f"SL/TP basarisiz ({len(sl_tp_fail)}): {', '.join(sl_tp_fail)}")

        run = await run_and_persist_reconciliation(session, admin.id, settings.mode, triggered_by="sync_sl_tp")
        print(f"\nReconciliation: {run.status}, mismatches={run.mismatches_found}, external={run.external_positions_found}")

        runtime = (
            await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin.id))
        ).scalar_one_or_none()
        if runtime is not None:
            print(f"Bot durumu: {runtime.run_state}")
            if runtime.safe_mode_reason:
                print(f"Safe mode: {runtime.safe_mode_reason}")
            elif run.status == "OK":
                runtime.run_state = "RUNNING"
                runtime.safe_mode_reason = None
                await session.commit()
                print("Bot RUNNING yapildi.")


if __name__ == "__main__":
    asyncio.run(main())

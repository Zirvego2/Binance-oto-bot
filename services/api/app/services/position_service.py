"""Pozisyon kapatma servisi (sartname bolum 13, 20, 22).

Bu fonksiyon idempotenttir: zaten CLOSED/CLOSING durumundaki bir pozisyon
icin cagirilirsa tekrar islem yapmaz (cift kapanis engellenir).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceApiError, BinanceConnectionError
from shared.binance.types import PlaceOrderRequest
from shared.client_ids import generate_client_order_id
from shared.db import AlgoOrder, Position, Trade
from shared.tenant_scope import get_or_create_daily_statistic
from shared.enums import PositionSide
from shared.roi import compute_realized_pnl
from shared.telegram_delivery import deliver_position_closed_notification

from ..core.binance_client import get_binance_adapter
from ..core.config import get_settings
from .audit_service import record_audit_log
from .settings_service import get_or_create_bot_settings


class PositionAlreadyClosedError(Exception):
    pass


async def close_position_manually(
    session: AsyncSession,
    position_id: str,
    admin_id: str | None,
    close_reason: str,
    ip_address: str | None = None,
) -> Position:
    result = await session.execute(select(Position).where(Position.id == position_id))
    position = result.scalar_one_or_none()
    if position is None:
        raise ValueError("Pozisyon bulunamadi")

    if position.status in ("CLOSED",):
        raise PositionAlreadyClosedError("Pozisyon zaten kapatilmis")
    if position.status == "CLOSING":
        raise PositionAlreadyClosedError("Pozisyon kapatma islemi zaten surmekte")

    position.status = "CLOSING"
    await session.commit()

    adapter = get_binance_adapter(position.bot_mode)
    close_side = "SELL" if position.side == "LONG" else "BUY"

    exit_price = position.mark_price or position.entry_price
    try:
        order_request = PlaceOrderRequest(
            symbol=position.symbol,
            side=close_side,
            quantity=position.quantity,
            client_order_id=generate_client_order_id("close"),
            reduce_only=True,
        )
        exchange_order = await adapter.place_reduce_only_market_order(order_request)
        exit_price = exchange_order.avg_price if exchange_order.avg_price > 0 else exit_price
    except (BinanceApiError, BinanceConnectionError):
        # Kapanis emri gonderilemedi - pozisyonu tekrar OPEN yap, admin'e bildir.
        position.status = "OPEN"
        await session.commit()
        raise

    for algo_id in filter(None, [position.stop_loss_algo_order_id, position.take_profit_algo_order_id]):
        try:
            await adapter.cancel_algo_order(position.symbol, algo_id)
        except (BinanceApiError, BinanceConnectionError):
            pass
        algo_result = await session.execute(select(AlgoOrder).where(AlgoOrder.client_algo_id == algo_id))
        algo_row = algo_result.scalar_one_or_none()
        if algo_row is not None and algo_row.status not in ("CANCELED", "FILLED"):
            algo_row.status = "CANCELED"
            algo_row.canceled_at = datetime.now(timezone.utc)

    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    gross_pnl = compute_realized_pnl(position.entry_price, exit_price, position.quantity, side_enum)
    close_commission = position.quantity * exit_price * Decimal("0.0004")
    net_pnl = gross_pnl - position.open_commission_usdt - close_commission - position.funding_fee_usdt
    margin = position.margin_usdt
    gross_roi = (gross_pnl / margin * 100) if margin else Decimal("0")
    net_roi = (net_pnl / margin * 100) if margin else Decimal("0")

    now = datetime.now(timezone.utc)
    position.status = "CLOSED"
    position.exit_price = exit_price
    position.close_reason = close_reason
    position.close_commission_usdt = close_commission
    position.roi_pct = net_roi
    position.closed_at = now

    trade = Trade(
        position_id=position.id,
        symbol=position.symbol,
        side=position.side,
        bot_mode=position.bot_mode,
        admin_id=position.admin_id,
        entry_price=position.entry_price,
        exit_price=exit_price,
        margin_usdt=position.margin_usdt,
        leverage=position.leverage,
        quantity=position.quantity,
        notional_usdt=position.notional_usdt,
        gross_pnl_usdt=gross_pnl,
        open_commission_usdt=position.open_commission_usdt,
        close_commission_usdt=close_commission,
        funding_fee_usdt=position.funding_fee_usdt,
        net_pnl_usdt=net_pnl,
        gross_roi_pct=gross_roi,
        net_roi_pct=net_roi,
        open_reason=position.open_reason,
        close_reason=close_reason,
        stop_loss_price=position.stop_loss_price,
        take_profit_price=position.take_profit_price,
        binance_order_id_open=position.open_order_id,
        binance_order_id_close=exchange_order.binance_order_id,
        client_order_id_open=position.open_order_id,
        client_order_id_close=exchange_order.client_order_id,
        opened_at=position.opened_at,
        closed_at=now,
    )
    session.add(trade)

    await _update_daily_statistics(
        session,
        admin_id,
        position.bot_mode,
        net_pnl,
        close_commission + position.open_commission_usdt,
        position.funding_fee_usdt,
    )

    await record_audit_log(
        session,
        admin_id=admin_id,
        action="CLOSE_POSITION",
        entity_type="position",
        entity_id=position.id,
        after_data={"close_reason": close_reason, "net_pnl_usdt": str(net_pnl)},
        ip_address=ip_address,
    )

    await session.flush()
    await session.commit()
    await session.refresh(position)
    await session.refresh(trade)

    from shared.firestore.tenant_sync import sync_tenant_position_closed

    await sync_tenant_position_closed(position.admin_id, position, trade)

    try:
        api_settings = get_settings()
        await deliver_position_closed_notification(
            session,
            api_settings,
            position.admin_id,
            source="api",
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            net_pnl_usdt=net_pnl,
            net_roi_pct=net_roi,
            close_reason=close_reason,
            bot_mode=position.bot_mode,
            opened_at=position.opened_at,
            closed_at=now,
            position_id=position.id,
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        pass
    return position


async def close_all_positions_emergency(
    session: AsyncSession,
    admin_id: str | None,
    password: str,
    expected_password: str,
    ip_address: str | None,
) -> dict:
    if password != expected_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acil kapatma sifresi hatali")

    settings_row = await get_or_create_bot_settings(session, admin_id or "")
    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == settings_row.mode,
            Position.admin_id == admin_id,
        )
    )
    open_positions = result.scalars().all()

    closed_positions: list[str] = []
    failed_positions: list[str] = []

    for position in open_positions:
        try:
            await close_position_manually(session, position.id, admin_id, "EMERGENCY_CLOSE", ip_address)
            closed_positions.append(position.symbol)
        except Exception:
            failed_positions.append(position.symbol)

    await record_audit_log(
        session,
        admin_id=admin_id,
        action="EMERGENCY_CLOSE_ALL",
        entity_type="position",
        after_data={"closed": closed_positions, "failed": failed_positions},
        ip_address=ip_address,
    )

    return {
        "closed_positions": closed_positions,
        "failed_positions": failed_positions,
        "closed_count": len(closed_positions),
    }


async def _update_daily_statistics(
    session: AsyncSession,
    admin_id: str,
    bot_mode: str,
    net_pnl: Decimal,
    commission: Decimal,
    funding: Decimal,
) -> None:
    stat = await get_or_create_daily_statistic(session, admin_id, bot_mode)

    stat.trades_count += 1
    if net_pnl > 0:
        stat.winning_trades += 1
        stat.consecutive_losses = 0
    else:
        stat.losing_trades += 1
        stat.consecutive_losses += 1
    stat.gross_pnl_usdt += net_pnl + commission + funding
    stat.net_pnl_usdt += net_pnl
    stat.total_commission_usdt += commission
    stat.total_funding_usdt += funding
    if stat.trades_count:
        stat.win_rate_pct = Decimal(stat.winning_trades) / Decimal(stat.trades_count) * 100

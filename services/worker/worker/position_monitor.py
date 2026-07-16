"""Acik pozisyonlarin izlenmesi: anlik mark price / PnL guncelleme, cikis
algoritmasi (kar/zarar/trailing) ve borsa SL/TP ile kapanan pozisyonlarin
tespiti + sonuclandirilmasi (sartname bolum 13, 20, 27).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.binance.types import PlaceOrderRequest
from shared.client_ids import generate_client_order_id
from shared.db import AlgoOrder, BotEvent, BotSettings, Position, Symbol, Trade
from shared.enums import PositionSide
from shared.loss_add import is_normal_market_position, should_loss_add
from shared.position_exit import evaluate_position_exit
from shared.roi import compute_realized_pnl, compute_roi_from_prices
from shared.tenant_scope import get_or_create_daily_statistic, get_or_create_symbol_rule
from shared.tenant_settings import get_bot_settings_for_admin

from .order_engine import (
    PROTECTIVE_SETUP_GRACE_SECONDS,
    add_to_position_on_loss,
    refresh_position_protective_orders,
)

logger = logging.getLogger("worker.position_monitor")

# Trailing stop icin pozisyon basina gorulen en yuksek ROI (%). Worker yeniden
# baslatilirsa sifirlanir; mevcut ROI'den devam eder.
_peak_roi_by_position: dict[str, Decimal] = {}
_loss_add_in_progress: set[str] = set()
_sl_widened_for_loss_add: set[str] = set()
# Ayni pozisyon birden fazla izleme dongusunden (mark-tick, periyodik refresh,
# reconciliation) es zamanli kapatilmaya calisilirsa mukerrer Telegram mesaji
# ve mukerrer borsa emri gonderilmesini onlemek icin kullanilan kilit seti.
_closing_in_progress: set[str] = set()


def _register_open_position(position_id: str, roi_pct: Decimal) -> None:
    existing = _peak_roi_by_position.get(position_id, roi_pct)
    _peak_roi_by_position[position_id] = existing if existing > roi_pct else roi_pct


def _unregister_position(position_id: str) -> None:
    _peak_roi_by_position.pop(position_id, None)


async def _is_still_open_in_db(session: AsyncSession, position_id: str) -> bool:
    """Baska bir oturumun bu pozisyonu zaten kapatip kapatmadigini, bellekteki
    (bayat olabilecek) position.status degerine guvenmeden veritabanindan
    taze olarak dogrular."""
    current_status = (
        await session.execute(select(Position.status).where(Position.id == position_id))
    ).scalar_one_or_none()
    return current_status == "OPEN"


async def refresh_open_positions(
    session: AsyncSession, adapter: BinanceFuturesAdapter, bot_mode: str, admin_id: str
) -> None:
    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == bot_mode,
            Position.admin_id == admin_id,
        )
    )
    local_positions = result.scalars().all()
    if not local_positions:
        return

    settings_row = await get_bot_settings_for_admin(session, admin_id)

    exchange_positions = await adapter.get_open_positions()
    exchange_by_symbol = {p.symbol: p for p in exchange_positions}

    for position in local_positions:
        exch = exchange_by_symbol.get(position.symbol)
        if exch is not None:
            await _sync_position_from_exchange(position, exch)
            _register_open_position(position.id, position.roi_pct)
            if settings_row is not None:
                await _maybe_widen_sl_for_loss_add(session, adapter, position, settings_row)
                closed = await _evaluate_and_maybe_close(session, adapter, position, settings_row)
                if closed:
                    continue
        else:
            await _finalize_closed_position(session, adapter, position)

    await session.commit()


async def reconcile_positions_from_exchange(
    session: AsyncSession, adapter: BinanceFuturesAdapter, bot_mode: str, admin_id: str
) -> tuple[list[str], int]:
    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == bot_mode,
            Position.admin_id == admin_id,
        )
    )
    local_positions = result.scalars().all()
    if not local_positions:
        return [], 0

    exchange_positions = await adapter.get_open_positions()
    exchange_by_symbol = {p.symbol: p for p in exchange_positions}
    closed_ghosts: list[str] = []

    for position in local_positions:
        exch = exchange_by_symbol.get(position.symbol)
        if exch is not None:
            await _sync_position_from_exchange(position, exch)
            _register_open_position(position.id, position.roi_pct)
        else:
            await _finalize_closed_position(session, adapter, position)
            closed_ghosts.append(position.symbol)
            _unregister_position(position.id)

    await session.commit()
    return closed_ghosts, len(exchange_positions)


async def process_position_on_mark_tick(
    session: AsyncSession,
    bot_mode: str,
    symbol: str,
    mark_price: Decimal,
    *,
    worker_settings=None,
) -> None:
    """WebSocket mark price tick'i geldiginde ilgili acik pozisyonlari degerlendirir."""

    from .tenant_ops import build_adapter_for_admin

    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == bot_mode,
            Position.symbol == symbol,
        )
    )
    positions = result.scalars().all()
    if not positions:
        return

    if worker_settings is None:
        from .config import get_worker_settings

        worker_settings = get_worker_settings()

    for position in positions:
        admin_id = position.admin_id
        if not admin_id:
            continue
        settings_row = await get_bot_settings_for_admin(session, admin_id)
        if settings_row is None:
            continue

        try:
            adapter = await build_adapter_for_admin(session, worker_settings, admin_id, bot_mode)
        except Exception:  # noqa: BLE001
            continue

        side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
        position.mark_price = mark_price
        position.roi_pct = compute_roi_from_prices(
            position.entry_price, mark_price, position.quantity, Decimal(position.leverage), side_enum
        )
        gross = (
            (mark_price - position.entry_price) * position.quantity
            if position.side == "LONG"
            else (position.entry_price - mark_price) * position.quantity
        )
        position.unrealized_pnl = gross

        on_mark_price_update = getattr(adapter, "on_mark_price_update", None)
        if on_mark_price_update is not None:
            await on_mark_price_update(symbol, mark_price)
            exchange_positions = await adapter.get_open_positions()
            if not any(p.symbol == symbol for p in exchange_positions):
                await _finalize_closed_position(session, adapter, position)
                _unregister_position(position.id)
                continue

        _register_open_position(position.id, position.roi_pct)
        await _evaluate_and_maybe_close(session, adapter, position, settings_row)

    await session.commit()


async def _maybe_widen_sl_for_loss_add(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    position: Position,
    settings_row: BotSettings,
) -> None:
    """Mevcut acik pozisyonlarda ekleme modu icin SL'yi bir kez genisletir."""
    if position.id in _sl_widened_for_loss_add:
        return
    if not getattr(settings_row, "loss_add_enabled", False):
        return
    if not is_normal_market_position(is_external=position.is_external, open_reason=position.open_reason):
        return
    loss_add_count = int(getattr(position, "loss_add_count", 0) or 0)
    if loss_add_count <= 0:
        return
    if loss_add_count >= int(getattr(settings_row, "loss_add_max_count", 0)):
        return
    if not position.protective_orders_ok:
        return
    if position.opened_at is not None:
        grace_end = position.opened_at.replace(tzinfo=timezone.utc) if position.opened_at.tzinfo is None else position.opened_at
        if datetime.now(timezone.utc) - grace_end < timedelta(seconds=PROTECTIVE_SETUP_GRACE_SECONDS):
            return

    symbol_result = await session.execute(select(Symbol).where(Symbol.symbol == position.symbol))
    symbol_row = symbol_result.scalar_one_or_none()
    if symbol_row is None:
        return

    ok = await refresh_position_protective_orders(session, adapter, settings_row, position, symbol_row)
    if ok:
        _sl_widened_for_loss_add.add(position.id)
        logger.info("%s zarar ekleme modu: SL/TP guncellendi (genis SL)", position.symbol)


async def _sync_position_from_exchange(position: Position, exch) -> None:
    if exch.quantity and exch.quantity > 0:
        position.quantity = exch.quantity
    if exch.entry_price and exch.entry_price > 0:
        position.entry_price = exch.entry_price
        position.notional_usdt = exch.entry_price * position.quantity
    position.mark_price = exch.mark_price
    position.unrealized_pnl = exch.unrealized_pnl
    position.liquidation_price = exch.liquidation_price or position.liquidation_price
    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    position.roi_pct = compute_roi_from_prices(
        position.entry_price, exch.mark_price, position.quantity, Decimal(position.leverage), side_enum
    )
    if exch.isolated_margin and exch.isolated_margin > 0:
        position.margin_ratio_pct = (
            (exch.isolated_margin - exch.unrealized_pnl) / exch.isolated_margin * Decimal("100")
            if exch.unrealized_pnl < 0
            else Decimal("0")
        )


async def _evaluate_and_maybe_close(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    position: Position,
    settings_row: BotSettings,
) -> bool:
    """Cikis algoritmasini calistirir; kapatma gerekiyorsa True doner."""

    peak = _peak_roi_by_position.get(position.id, position.roi_pct)
    loss_add_trigger = getattr(settings_row, "loss_add_trigger_roi_pct", settings_row.stop_loss_roi_pct)

    if should_loss_add(
        position.roi_pct,
        loss_add_trigger_roi_pct=loss_add_trigger,
        stop_loss_roi_pct=settings_row.stop_loss_roi_pct,
        loss_add_enabled=getattr(settings_row, "loss_add_enabled", False),
        loss_add_max_count=int(getattr(settings_row, "loss_add_max_count", 0)),
        loss_add_count=int(getattr(position, "loss_add_count", 0) or 0),
        is_normal_position=is_normal_market_position(
            is_external=position.is_external,
            open_reason=position.open_reason,
        ),
    ):
        if position.id not in _loss_add_in_progress:
            _loss_add_in_progress.add(position.id)
            try:
                symbol_result = await session.execute(
                    select(Symbol).where(Symbol.symbol == position.symbol)
                )
                symbol_row = symbol_result.scalar_one_or_none()
                if symbol_row is not None:
                    added = await add_to_position_on_loss(
                        session, adapter, settings_row, position, symbol_row
                    )
                    if added:
                        _peak_roi_by_position[position.id] = position.roi_pct
                        logger.info(
                            "%s zarar esiginde ekleme yapildi (ROI=%.2f%%, ekleme=%s)",
                            position.symbol, position.roi_pct, position.loss_add_count,
                        )
                        return False
            finally:
                _loss_add_in_progress.discard(position.id)

    decision, updated_peak = evaluate_position_exit(
        position.roi_pct,
        peak,
        take_profit_roi_pct=settings_row.take_profit_roi_pct,
        stop_loss_roi_pct=settings_row.stop_loss_roi_pct,
        trailing_stop_enabled=settings_row.trailing_stop_enabled,
        trailing_stop_activation_roi_pct=settings_row.trailing_stop_activation_roi_pct,
        trailing_stop_callback_rate_pct=settings_row.trailing_stop_callback_rate_pct,
    )
    _peak_roi_by_position[position.id] = updated_peak

    if not decision.should_close or decision.close_reason is None:
        return False

    logger.info(
        "%s pozisyon cikis sinyali: %s (ROI=%.2f%%, zirve=%.2f%%)",
        position.symbol, decision.close_reason, position.roi_pct, updated_peak,
    )
    await _software_close_position(session, adapter, position, decision.close_reason)
    return True


async def _software_close_position(
    session: AsyncSession, adapter: BinanceFuturesAdapter, position: Position, close_reason: str
) -> None:
    """Algoritma tetiklemesiyle pozisyonu piyasa emriyle kapatir."""

    if position.status != "OPEN" or position.id in _closing_in_progress:
        return
    _closing_in_progress.add(position.id)
    try:
        if not await _is_still_open_in_db(session, position.id):
            logger.info("%s pozisyonu baska bir dongu tarafindan zaten kapatildi, atlaniyor", position.symbol)
            _unregister_position(position.id)
            return

        position.status = "CLOSING"
        await session.flush()

        for algo_id in filter(None, [position.stop_loss_algo_order_id, position.take_profit_algo_order_id]):
            try:
                await adapter.cancel_algo_order(position.symbol, algo_id)
            except Exception:  # noqa: BLE001
                pass
            algo_row_result = await session.execute(select(AlgoOrder).where(AlgoOrder.client_algo_id == algo_id))
            algo_row = algo_row_result.scalar_one_or_none()
            if algo_row is not None and algo_row.status not in ("CANCELED", "FILLED"):
                algo_row.status = "CANCELED"
                algo_row.canceled_at = datetime.now(timezone.utc)

        close_side = "SELL" if position.side == "LONG" else "BUY"
        exit_price = position.mark_price or position.entry_price
        try:
            exchange_order = await adapter.place_reduce_only_market_order(
                PlaceOrderRequest(
                    symbol=position.symbol,
                    side=close_side,
                    quantity=position.quantity,
                    client_order_id=generate_client_order_id("exit"),
                    reduce_only=True,
                )
            )
            exit_price = exchange_order.avg_price if exchange_order.avg_price > 0 else exit_price
        except Exception as exc:  # noqa: BLE001
            position.status = "OPEN"
            await session.flush()
            logger.error("%s yazilim kapatma emri basarisiz: %s", position.symbol, exc)
            raise

        await _record_closed_position(session, position, exit_price, close_reason)
        _unregister_position(position.id)
    finally:
        _closing_in_progress.discard(position.id)


async def _finalize_closed_position(session: AsyncSession, adapter: BinanceFuturesAdapter, position: Position) -> None:
    if position.status != "OPEN" or position.id in _closing_in_progress:
        return
    _closing_in_progress.add(position.id)
    try:
        if not await _is_still_open_in_db(session, position.id):
            logger.info("%s pozisyonu baska bir dongu tarafindan zaten kapatildi, atlaniyor", position.symbol)
            _unregister_position(position.id)
            return

        close_reason = "UNKNOWN"
        exit_price = position.mark_price or position.entry_price

        for algo_id, purpose in (
            (position.stop_loss_algo_order_id, "STOP_LOSS"),
            (position.take_profit_algo_order_id, "TAKE_PROFIT"),
        ):
            if not algo_id:
                continue
            try:
                algo_order = await adapter.query_algo_order(position.symbol, algo_id)
            except Exception:  # noqa: BLE001
                continue
            algo_row_result = await session.execute(select(AlgoOrder).where(AlgoOrder.client_algo_id == algo_id))
            algo_row = algo_row_result.scalar_one_or_none()
            if algo_order is not None and algo_order.status == "FILLED":
                close_reason = purpose
                exit_price = algo_order.avg_price if algo_order.avg_price > 0 else exit_price
                if algo_row is not None:
                    algo_row.status = "FILLED"
                    algo_row.triggered_at = datetime.now(timezone.utc)
            elif algo_row is not None and algo_row.status not in ("CANCELED", "FILLED"):
                try:
                    await adapter.cancel_algo_order(position.symbol, algo_id)
                except Exception:  # noqa: BLE001
                    pass
                algo_row.status = "CANCELED"
                algo_row.canceled_at = datetime.now(timezone.utc)

        await _record_closed_position(session, position, exit_price, close_reason)
        _unregister_position(position.id)
    finally:
        _closing_in_progress.discard(position.id)


async def _send_close_telegram(
    session: AsyncSession,
    position: Position,
    exit_price: Decimal,
    net_pnl: Decimal,
    net_roi: Decimal,
    close_reason: str,
    closed_at: datetime,
) -> None:
    try:
        from .config import get_worker_settings
        from .tenant_ops import send_position_closed_notification

        worker_settings = get_worker_settings()
        await send_position_closed_notification(
            session,
            worker_settings,
            position.admin_id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            net_pnl_usdt=net_pnl,
            net_roi_pct=net_roi,
            close_reason=close_reason,
            bot_mode=position.bot_mode,
            opened_at=position.opened_at,
            closed_at=closed_at,
            position_id=position.id,
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram kapanis bildirimi gonderilemedi: %s", exc)


async def _record_closed_position(
    session: AsyncSession, position: Position, exit_price: Decimal, close_reason: str
) -> None:
    from sqlalchemy import select

    existing_trade = (
        await session.execute(select(Trade).where(Trade.position_id == position.id))
    ).scalar_one_or_none()

    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    gross_pnl = compute_realized_pnl(position.entry_price, exit_price, position.quantity, side_enum)
    close_commission = position.quantity * exit_price * Decimal("0.0004")
    net_pnl = gross_pnl - position.open_commission_usdt - close_commission - position.funding_fee_usdt
    margin = position.margin_usdt
    net_roi = (net_pnl / margin * 100) if margin else Decimal("0")

    now = datetime.now(timezone.utc)
    position.status = "CLOSED"
    position.exit_price = exit_price
    position.close_reason = close_reason
    position.close_commission_usdt = close_commission
    position.roi_pct = net_roi
    position.closed_at = now

    if existing_trade is not None:
        logger.info(
            "%s pozisyonu zaten kapanmis (trade mevcut), DB durumu CLOSED yapildi",
            position.symbol,
        )
        await session.flush()
        await _send_close_telegram(
            session,
            position,
            exit_price,
            existing_trade.net_pnl_usdt,
            existing_trade.net_roi_pct,
            close_reason,
            now,
        )
        return

    trade = Trade(
        position_id=position.id, symbol=position.symbol, side=position.side, bot_mode=position.bot_mode,
        admin_id=position.admin_id,
        entry_price=position.entry_price, exit_price=exit_price, margin_usdt=position.margin_usdt,
        leverage=position.leverage, quantity=position.quantity, notional_usdt=position.notional_usdt,
        gross_pnl_usdt=gross_pnl, open_commission_usdt=position.open_commission_usdt,
        close_commission_usdt=close_commission, funding_fee_usdt=position.funding_fee_usdt, net_pnl_usdt=net_pnl,
        gross_roi_pct=(gross_pnl / margin * 100) if margin else Decimal("0"), net_roi_pct=net_roi,
        open_reason=position.open_reason, close_reason=close_reason, stop_loss_price=position.stop_loss_price,
        take_profit_price=position.take_profit_price, binance_order_id_open=position.open_order_id,
        opened_at=position.opened_at, closed_at=now,
    )
    session.add(trade)
    await session.flush()

    from shared.firestore.tenant_sync import sync_tenant_position_closed

    await sync_tenant_position_closed(position.admin_id, position, trade)

    session.add(
        BotEvent(
            event_type="POSITION_CLOSED",
            message=f"{position.symbol} pozisyonu {close_reason} nedeniyle kapandi (net PnL={net_pnl})",
            bot_mode=position.bot_mode,
            details={"symbol": position.symbol, "close_reason": close_reason, "net_pnl_usdt": str(net_pnl)},
        )
    )

    await _update_daily_statistics(session, position.admin_id or "", position.bot_mode, net_pnl)
    await _apply_cooldown(session, position.admin_id or "", position.symbol)
    await _refresh_symbol_profile(session, position.admin_id or "", position.symbol)

    await _send_close_telegram(session, position, exit_price, net_pnl, net_roi, close_reason, now)


async def _refresh_symbol_profile(session: AsyncSession, admin_id: str, symbol: str) -> None:
    settings_row = await get_bot_settings_for_admin(session, admin_id)
    if settings_row is None or not getattr(settings_row, "symbol_profile_enabled", True):
        return
    try:
        from shared.enhanced.symbol_profile import refresh_symbol_profile

        await refresh_symbol_profile(
            session,
            symbol,
            min_sample=int(getattr(settings_row, "minimum_profile_sample_size", 10)),
        )
    except Exception:  # noqa: BLE001
        logger.warning("%s profil yenileme basarisiz", symbol, exc_info=True)


async def _update_daily_statistics(
    session: AsyncSession, admin_id: str, bot_mode: str, net_pnl: Decimal
) -> None:
    stat = await get_or_create_daily_statistic(session, admin_id, bot_mode)

    stat.trades_count += 1
    if net_pnl > 0:
        stat.winning_trades += 1
        stat.consecutive_losses = 0
    else:
        stat.losing_trades += 1
        stat.consecutive_losses += 1
    stat.net_pnl_usdt += net_pnl
    stat.gross_pnl_usdt += net_pnl
    if stat.trades_count:
        stat.win_rate_pct = Decimal(stat.winning_trades) / Decimal(stat.trades_count) * 100


async def _apply_cooldown(session: AsyncSession, admin_id: str, symbol: str) -> None:
    settings_row = await get_bot_settings_for_admin(session, admin_id)
    cooldown_minutes = settings_row.post_trade_cooldown_minutes if settings_row else 30

    rule = await get_or_create_symbol_rule(session, admin_id, symbol)
    now = datetime.now(timezone.utc)
    rule.cooldown_until = now + timedelta(minutes=cooldown_minutes)
    rule.last_trade_at = now

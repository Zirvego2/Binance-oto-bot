"""Pozisyon acma motoru: boyutlandirma, emir gonderme, ROI tabanli SL/TP
koruyucu emirlerin YERLESTIRILMESI (sartname bolum 10-14).

KRITIK KURAL: Bir pozisyon, hem stop-loss hem take-profit emri BORSA
TARAFINDA basariyla yerlesmeden "korumali" sayilmaz. Bu emirlerden biri
basarisiz olursa pozisyon HEMEN (reduce-only market emriyle) kapatilir;
korumasiz pozisyon asla acik birakilmaz.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.errors import BinanceApiError
from shared.binance.interface import BinanceFuturesAdapter
from shared.binance.types import ExchangeOrder, PlaceAlgoOrderRequest, PlaceOrderRequest
from shared.binance_filters import SymbolFilters
from shared.client_ids import generate_client_algo_id, generate_client_order_id
from shared.db import AlgoOrder, BotEvent, BotRuntimeStatus, Order, Position, RiskEvent, Symbol
from shared.decimal_utils import ZERO, quantize_price
from shared.enums import PositionSide
from shared.loss_add import effective_stop_loss_roi_pct
from shared.position_sizing import PositionSizingInputs, calculate_position_size
from shared.roi import RoiPriceInputs, compute_roi_from_prices, compute_roi_prices, estimate_liquidation_price, liquidation_distance_pct
from shared.tenant_scope import get_or_create_symbol_rule
from shared.trade_overrides import TradeOpenOverrides, apply_trade_overrides

from .risk import check_liquidation_distance
from .strategy import evaluate_live_signal_score
from .symbol_filters import build_symbol_filters

logger = logging.getLogger("worker.order_engine")

ORDER_FILL_MAX_ATTEMPTS = 10
ORDER_FILL_POLL_INTERVAL_SEC = 1.0
PROTECTIVE_ORDER_MAX_ATTEMPTS = 10
PROTECTIVE_ORDER_RETRY_INTERVAL_SEC = 1.0
PROTECTIVE_SETUP_GRACE_SECONDS = 90
DUPLICATE_PROTECTIVE_ORDER_CODE = -4130
LIMIT_ENTRY_POLL_INTERVAL_SEC = 30.0  # Olta emri durumu 30 saniyede bir kontrol edilir


class PositionOpenSkipped(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _exchange_sl_roi_pct(settings_row, loss_add_count: int) -> Decimal:
    return effective_stop_loss_roi_pct(
        settings_row.stop_loss_roi_pct,
        loss_add_enabled=getattr(settings_row, "loss_add_enabled", False),
        loss_add_max_count=int(getattr(settings_row, "loss_add_max_count", 0)),
        loss_add_count=loss_add_count,
    )


async def _cancel_position_protective_orders(
    session: AsyncSession, adapter: BinanceFuturesAdapter, position: Position
) -> None:
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
    try:
        await adapter.cancel_all_open_orders(position.symbol)
    except Exception:  # noqa: BLE001
        pass
    position.stop_loss_algo_order_id = None
    position.take_profit_algo_order_id = None
    position.protective_orders_ok = False


def _is_duplicate_protective_order_error(exc: Exception | None) -> bool:
    return isinstance(exc, BinanceApiError) and exc.code == DUPLICATE_PROTECTIVE_ORDER_CODE


def _classify_open_algo_order(order: ExchangeOrder) -> str | None:
    order_type = (order.order_type or "").upper()
    if "TAKE_PROFIT" in order_type:
        return "TAKE_PROFIT"
    if "STOP" in order_type:
        return "STOP_LOSS"
    return None


async def _find_open_protective_algo(
    adapter: BinanceFuturesAdapter, symbol: str, purpose: str
) -> ExchangeOrder | None:
    for order in await adapter.get_open_algo_orders(symbol):
        if not order.close_position:
            continue
        if _classify_open_algo_order(order) == purpose:
            return order
    return None


async def _exchange_has_both_protective_orders(
    adapter: BinanceFuturesAdapter, symbol: str
) -> tuple[bool, bool]:
    sl_found = False
    tp_found = False
    for order in await adapter.get_open_algo_orders(symbol):
        if not order.close_position:
            continue
        kind = _classify_open_algo_order(order)
        if kind == "STOP_LOSS":
            sl_found = True
        elif kind == "TAKE_PROFIT":
            tp_found = True
    return sl_found, tp_found


async def _attach_existing_protective_algo(
    session: AsyncSession,
    position: Position,
    purpose: str,
    exchange_order: ExchangeOrder,
    settings_row,
    algo_row: AlgoOrder | None = None,
) -> AlgoOrder:
    close_side = "SELL" if position.side == "LONG" else "BUY"
    order_type = "STOP_MARKET" if purpose == "STOP_LOSS" else "TAKE_PROFIT_MARKET"
    client_algo_id = exchange_order.client_order_id or generate_client_algo_id(
        "sl" if purpose == "STOP_LOSS" else "tp"
    )

    existing_result = await session.execute(
        select(AlgoOrder).where(AlgoOrder.client_algo_id == client_algo_id)
    )
    row = existing_result.scalar_one_or_none()
    if row is None and algo_row is not None:
        row = algo_row
        row.client_algo_id = client_algo_id
    if row is None:
        row = AlgoOrder(
            position_id=position.id,
            symbol=position.symbol,
            purpose=purpose,
            side=close_side,
            order_type=order_type,
            trigger_price=exchange_order.stop_price or ZERO,
            working_type=settings_row.working_type,
            close_position=True,
            client_algo_id=client_algo_id,
            status="NEW",
            bot_mode=settings_row.mode,
        )
        session.add(row)

    row.status = "NEW"
    row.binance_order_id = exchange_order.binance_order_id
    if exchange_order.stop_price and exchange_order.stop_price > ZERO:
        row.trigger_price = exchange_order.stop_price
    row.last_error = None
    await session.flush()
    return row


async def _try_recover_protective_orders_on_exchange(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    position: Position,
    settings_row,
    sl_algo: AlgoOrder | None = None,
    tp_algo: AlgoOrder | None = None,
) -> tuple[bool, AlgoOrder | None, AlgoOrder | None]:
    sl_ex = await _find_open_protective_algo(adapter, position.symbol, "STOP_LOSS")
    tp_ex = await _find_open_protective_algo(adapter, position.symbol, "TAKE_PROFIT")
    if sl_ex is None or tp_ex is None:
        return False, None, None

    sl_row = await _attach_existing_protective_algo(
        session, position, "STOP_LOSS", sl_ex, settings_row, sl_algo
    )
    tp_row = await _attach_existing_protective_algo(
        session, position, "TAKE_PROFIT", tp_ex, settings_row, tp_algo
    )
    position.protective_orders_ok = True
    position.stop_loss_algo_order_id = sl_row.client_algo_id
    position.take_profit_algo_order_id = tp_row.client_algo_id
    await session.flush()
    logger.info("%s koruyucu emirler borsadan dogrulandi (SL+TP mevcut)", position.symbol)
    return True, sl_row, tp_row


async def _finalize_protective_orders_or_emergency_close(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    position: Position,
    settings_row,
    sl_ok: bool,
    tp_ok: bool,
    sl_algo: AlgoOrder | None,
    tp_algo: AlgoOrder | None,
) -> tuple[AlgoOrder, AlgoOrder]:
    if sl_ok and tp_ok and sl_algo is not None and tp_algo is not None:
        return sl_algo, tp_algo

    recovered, recovered_sl, recovered_tp = await _try_recover_protective_orders_on_exchange(
        session, adapter, position, settings_row, sl_algo, tp_algo
    )
    if recovered and recovered_sl is not None and recovered_tp is not None:
        await session.commit()
        return recovered_sl, recovered_tp

    await _emergency_close_unprotected(session, adapter, position, settings_row)
    raise PositionOpenSkipped("protective_order_placement_failed")


async def refresh_position_protective_orders(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    position: Position,
    symbol_row: Symbol,
    filters: SymbolFilters | None = None,
) -> bool:
    """Mevcut pozisyon icin SL/TP emirlerini guncel giris fiyatina gore yeniler."""
    if filters is None:
        filters = build_symbol_filters(symbol_row)
    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    loss_add_count = int(getattr(position, "loss_add_count", 0) or 0)
    sl_roi = _exchange_sl_roi_pct(settings_row, loss_add_count)

    roi_result = compute_roi_prices(
        RoiPriceInputs(
            entry_price=position.entry_price,
            quantity=position.quantity,
            side=side_enum,
            leverage=Decimal(position.leverage),
            take_profit_roi_pct=settings_row.take_profit_roi_pct,
            stop_loss_roi_pct=sl_roi,
            taker_commission_rate=settings_row.paper_taker_commission_rate,
        )
    )
    stop_loss_price = _round_protective_trigger_price(
        filters, roi_result.stop_loss_price, position.side, "STOP_LOSS"
    )
    take_profit_price = _round_protective_trigger_price(
        filters, roi_result.take_profit_price, position.side, "TAKE_PROFIT"
    )

    await _cancel_position_protective_orders(session, adapter, position)

    sl_ok, sl_algo = await _place_protective_order(
        session, adapter, position, "STOP_LOSS", stop_loss_price, settings_row, filters
    )
    tp_ok, tp_algo = await _place_protective_order(
        session, adapter, position, "TAKE_PROFIT", take_profit_price, settings_row, filters
    )
    if not (sl_ok and tp_ok):
        position.stop_loss_price = stop_loss_price
        position.take_profit_price = take_profit_price
        await session.flush()
        return False

    position.protective_orders_ok = True
    position.stop_loss_price = stop_loss_price
    position.take_profit_price = take_profit_price
    position.stop_loss_algo_order_id = sl_algo.client_algo_id
    position.take_profit_algo_order_id = tp_algo.client_algo_id
    await session.flush()
    return True


async def add_to_position_on_loss(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    position: Position,
    symbol_row: Symbol,
    *,
    purpose: str = "LOSS_ADD",
    event_note: str = "zarar esiginde",
) -> bool:
    """Acik pozisyona ilk acilista kullanilan marj kadar ekleme yapar."""
    filters = build_symbol_filters(symbol_row)
    mark_tick = await adapter.get_mark_price(position.symbol)
    price = mark_tick.mark_price

    balances = await adapter.get_account_balance()
    usdt_balance = next((b for b in balances if b.asset == "USDT"), None)
    available_balance = usdt_balance.available_balance if usdt_balance else ZERO

    sizing = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=settings_row.margin_per_trade_usdt,
            leverage=Decimal(position.leverage),
            price=price,
            filters=filters,
            available_balance_usdt=available_balance,
        )
    )
    if not sizing.ok:
        logger.warning("%s zarar ekleme atlandi: %s", position.symbol, sizing.reason)
        return False

    open_side = "BUY" if position.side == "LONG" else "SELL"
    client_id = generate_client_order_id("add")
    now = datetime.now(timezone.utc)

    order_row = Order(
        symbol=position.symbol,
        side=open_side,
        order_type="MARKET",
        purpose=purpose,
        quantity=sizing.quantity,
        client_order_id=client_id,
        status="SUBMITTING",
        bot_mode=settings_row.mode,
        position_id=position.id,
        submitted_at=now,
    )
    session.add(order_row)
    await session.flush()

    try:
        exchange_order = await adapter.place_market_order(
            PlaceOrderRequest(
                symbol=position.symbol,
                side=open_side,
                quantity=sizing.quantity,
                client_order_id=client_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        order_row.status = "FAILED"
        order_row.last_error = str(exc)[:512]
        await session.flush()
        logger.error("%s zarar ekleme emri basarisiz: %s", position.symbol, exc)
        return False

    old_qty = position.quantity
    old_entry = position.entry_price
    old_margin = position.margin_usdt
    old_loss_add_count = int(getattr(position, "loss_add_count", 0) or 0)
    old_commission = position.open_commission_usdt

    add_qty = exchange_order.executed_qty if exchange_order.executed_qty > ZERO else sizing.quantity
    fill_price = exchange_order.avg_price if exchange_order.avg_price > ZERO else price

    order_row.status = exchange_order.status
    order_row.binance_order_id = exchange_order.binance_order_id
    order_row.avg_fill_price = fill_price
    order_row.filled_quantity = add_qty
    order_row.filled_at = now if exchange_order.status == "FILLED" else None

    old_qty = position.quantity
    old_entry = position.entry_price
    total_qty = old_qty + add_qty
    position.entry_price = (old_entry * old_qty + fill_price * add_qty) / total_qty
    position.quantity = total_qty
    position.notional_usdt = position.entry_price * total_qty
    position.margin_usdt += settings_row.margin_per_trade_usdt
    position.open_commission_usdt += fill_price * add_qty * settings_row.paper_taker_commission_rate
    position.loss_add_count = int(getattr(position, "loss_add_count", 0) or 0) + 1
    position.mark_price = price

    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    position.roi_pct = compute_roi_from_prices(
        position.entry_price, price, position.quantity, Decimal(position.leverage), side_enum
    )

    protective_ok = await refresh_position_protective_orders(
        session, adapter, settings_row, position, symbol_row, filters
    )
    if not protective_ok:
        logger.error("%s zarar ekleme sonrasi koruyucu emirler yerlestirilemedi", position.symbol)
        revert_side = "SELL" if position.side == "LONG" else "BUY"
        try:
            await adapter.place_reduce_only_market_order(
                PlaceOrderRequest(
                    symbol=position.symbol,
                    side=revert_side,
                    quantity=add_qty,
                    client_order_id=generate_client_order_id("addrev"),
                    reduce_only=True,
                )
            )
            position.entry_price = old_entry
            position.quantity = old_qty
            position.notional_usdt = old_entry * old_qty
            position.margin_usdt = old_margin
            position.open_commission_usdt = old_commission
            position.loss_add_count = old_loss_add_count
            position.roi_pct = compute_roi_from_prices(
                position.entry_price, price, position.quantity, Decimal(position.leverage), side_enum
            )
            await refresh_position_protective_orders(
                session, adapter, settings_row, position, symbol_row, filters
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("%s ekleme geri alinamadi: %s", position.symbol, exc)
            position.protective_orders_ok = False
            await session.flush()
        return False

    await _record_bot_event(
        session,
        "POSITION_LOSS_ADD" if purpose == "LOSS_ADD" else "POSITION_MANUAL_ADD",
        (
            f"{position.symbol} {position.side} {event_note} eklendi "
            f"(+{add_qty}, yeni_giris={position.entry_price}, ekleme={position.loss_add_count})"
        ),
        settings_row.mode,
        {
            "symbol": position.symbol,
            "added_qty": str(add_qty),
            "new_entry_price": str(position.entry_price),
            "loss_add_count": position.loss_add_count,
        },
    )
    await session.flush()
    logger.info(
        "%s zarar ekleme tamamlandi: +%s | yeni_giris=%s | ekleme_sayisi=%s",
        position.symbol, add_qty, position.entry_price, position.loss_add_count,
    )
    return True


async def _record_risk_event(
    session: AsyncSession, event_type: str, symbol: str, severity: str, message: str, bot_mode: str
) -> None:
    session.add(RiskEvent(event_type=event_type, symbol=symbol, severity=severity, message=message, bot_mode=bot_mode))


async def _record_bot_event(session: AsyncSession, event_type: str, message: str, bot_mode: str, details: dict | None = None) -> None:
    session.add(BotEvent(event_type=event_type, message=message, bot_mode=bot_mode, details=details))


def _round_protective_trigger_price(
    filters: SymbolFilters, price: Decimal, position_side: str, purpose: str
) -> Decimal:
    """SL/TP tetik fiyatini sembol tickSize degerine yuvarlar (-1111 precision hatasini onler)."""
    tick = filters.price_tick_size
    if position_side == "LONG":
        rounding = ROUND_DOWN if purpose == "STOP_LOSS" else ROUND_UP
    else:
        rounding = ROUND_UP if purpose == "STOP_LOSS" else ROUND_DOWN
    return quantize_price(price, tick, rounding=rounding)


async def _abort_pending_open_order(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    symbol: str,
    client_order_id: str,
    side: str,
    exchange_order: ExchangeOrder,
    order_row: Order,
    bot_mode: str,
    reason: str,
) -> None:
    """Skor dusunce bekleyen emri iptal eder; kismi dolum varsa geri alir."""

    try:
        await adapter.cancel_order(symbol, client_order_id)
    except Exception:  # noqa: BLE001
        logger.warning("%s acilis emri iptal edilemedi: %s", symbol, client_order_id)

    if exchange_order.executed_qty > ZERO:
        close_side = "SELL" if side == "LONG" else "BUY"
        try:
            await adapter.place_reduce_only_market_order(
                PlaceOrderRequest(
                    symbol=symbol,
                    side=close_side,
                    quantity=exchange_order.executed_qty,
                    client_order_id=generate_client_order_id("scr"),
                    reduce_only=True,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("%s skor dususunde kismi dolum geri alinamadi", symbol)

    order_row.status = "CANCELED"
    order_row.filled_quantity = exchange_order.executed_qty
    await session.flush()
    await _record_risk_event(
        session, "SIGNAL_SCORE_CHANGED", symbol, "INFO",
        f"Acilis emri iptal edildi: {reason}", bot_mode,
    )
    await session.commit()


async def _validate_entry_signal_score(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    entry_score: Decimal,
) -> tuple[bool, str | None]:
    """Guncel skor hala giris skoruna esit/yuksek mi ve yon ayni mi kontrol eder."""

    live_result = await evaluate_live_signal_score(session, adapter, settings_row, symbol_row)
    if live_result is None or live_result.suggested_side is None:
        return False, "signal_no_longer_valid"
    if live_result.suggested_side != side:
        return False, "signal_side_changed"
    current_score = Decimal(str(live_result.breakdown.total_score))
    if current_score < entry_score:
        return False, "signal_score_dropped"
    return True, None


async def _await_order_fill(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    client_order_id: str,
    initial_order: ExchangeOrder,
    order_row: Order,
    entry_signal_score: Decimal | None,
) -> ExchangeOrder:
    """Acilis emrinin dolmasini en fazla 10 kez sorgular.

    Skor ayni veya yuksekse takibe devam eder; skor duserse veya yon degisirse
    emri iptal eder.
    """

    exchange_order = initial_order
    for attempt in range(ORDER_FILL_MAX_ATTEMPTS):
        if exchange_order.status == "FILLED" and exchange_order.executed_qty > ZERO:
            return exchange_order
        if exchange_order.status in ("CANCELED", "REJECTED", "EXPIRED"):
            break

        if entry_signal_score is not None:
            still_valid, invalid_reason = await _validate_entry_signal_score(
                session, adapter, settings_row, symbol_row, side, entry_signal_score
            )
            if not still_valid:
                await _abort_pending_open_order(
                    session, adapter, symbol_row.symbol, client_order_id, side,
                    exchange_order, order_row, settings_row.mode, invalid_reason or "signal_score_dropped",
                )
                raise PositionOpenSkipped(invalid_reason or "signal_score_dropped")

        if attempt < ORDER_FILL_MAX_ATTEMPTS - 1:
            await asyncio.sleep(ORDER_FILL_POLL_INTERVAL_SEC)
            queried = await adapter.query_order(symbol_row.symbol, client_order_id)
            if queried is not None:
                exchange_order = queried
                logger.info(
                    "%s acilis emri takip (%s/%s): status=%s filled=%s skor_kontrol=OK",
                    symbol_row.symbol, attempt + 2, ORDER_FILL_MAX_ATTEMPTS,
                    exchange_order.status, exchange_order.executed_qty,
                )
    if exchange_order.executed_qty > ZERO:
        return exchange_order
    raise PositionOpenSkipped("order_not_filled")


async def _pick_maintenance_margin_rate(adapter: BinanceFuturesAdapter, symbol: str, notional: Decimal) -> Decimal:
    try:
        brackets = await adapter.get_leverage_bracket(symbol)
    except Exception:  # noqa: BLE001
        return Decimal("0.005")
    if not brackets:
        return Decimal("0.005")
    for bracket in sorted(brackets, key=lambda b: b.bracket):
        if bracket.notional_floor <= notional < bracket.notional_cap or bracket.notional_cap == ZERO:
            return bracket.maint_margin_ratio
    return brackets[-1].maint_margin_ratio


async def _compute_open_at_leverage(
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    price: Decimal,
    filters: SymbolFilters,
    available_balance: Decimal,
    leverage: int,
    loss_add_count: int = 0,
) -> tuple[int, object, Decimal, Decimal, Decimal] | None:
    side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
    open_sl_roi = _exchange_sl_roi_pct(settings_row, loss_add_count)

    sizing = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=settings_row.margin_per_trade_usdt,
            leverage=Decimal(leverage),
            price=price,
            filters=filters,
            available_balance_usdt=available_balance,
        )
    )
    if not sizing.ok:
        return None

    maint_margin_rate = await _pick_maintenance_margin_rate(adapter, symbol_row.symbol, sizing.notional)
    estimated_liquidation = estimate_liquidation_price(price, Decimal(leverage), side_enum, maint_margin_rate)
    roi_result = compute_roi_prices(
        RoiPriceInputs(
            entry_price=price,
            quantity=sizing.quantity,
            side=side_enum,
            leverage=Decimal(leverage),
            take_profit_roi_pct=settings_row.take_profit_roi_pct,
            stop_loss_roi_pct=open_sl_roi,
            taker_commission_rate=settings_row.paper_taker_commission_rate,
        )
    )
    stop_loss_price = _round_protective_trigger_price(filters, roi_result.stop_loss_price, side, "STOP_LOSS")
    take_profit_price = _round_protective_trigger_price(filters, roi_result.take_profit_price, side, "TAKE_PROFIT")
    return leverage, sizing, stop_loss_price, take_profit_price, estimated_liquidation


async def _select_leverage_for_open(
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    price: Decimal,
    filters: SymbolFilters,
    available_balance: Decimal,
    requested_leverage: int,
    loss_add_count: int = 0,
) -> tuple[int, object, Decimal, Decimal, Decimal] | None:
    """Likidasyon mesafe kontrolunu gecen en yuksek kaldiraci secer."""
    side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT

    for try_lev in range(int(requested_leverage), 0, -1):
        computed = await _compute_open_at_leverage(
            adapter,
            settings_row,
            symbol_row,
            side,
            price,
            filters,
            available_balance,
            try_lev,
            loss_add_count,
        )
        if computed is None:
            continue

        _, _, stop_loss_price, _, estimated_liquidation = computed
        distance_pct = liquidation_distance_pct(stop_loss_price, estimated_liquidation, side_enum)
        if check_liquidation_distance(distance_pct, settings_row.min_liquidation_distance_pct).ok:
            if try_lev != requested_leverage:
                logger.info(
                    "%s icin kaldirac %sx -> %sx dusuruldu (likidasyon mesafe %%%.2f)",
                    symbol_row.symbol,
                    requested_leverage,
                    try_lev,
                    distance_pct,
                )
            return computed

    return None


async def _resolve_leverage_for_open(
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    price: Decimal,
    filters: SymbolFilters,
    available_balance: Decimal,
    requested_leverage: int,
    loss_add_count: int = 0,
) -> tuple[int, object, Decimal, Decimal, Decimal] | None:
    """risk_adjusted_leverage_enabled aciksa guvenli kaldirac secer; kapaliysa ayarli kaldiraci kullanir."""
    if getattr(settings_row, "risk_adjusted_leverage_enabled", False):
        return await _select_leverage_for_open(
            adapter,
            settings_row,
            symbol_row,
            side,
            price,
            filters,
            available_balance,
            requested_leverage,
            loss_add_count,
        )

    return await _compute_open_at_leverage(
        adapter,
        settings_row,
        symbol_row,
        side,
        price,
        filters,
        available_balance,
        int(requested_leverage),
        loss_add_count,
    )


async def open_position_for_signal(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    signal_id: str | None,
    open_reason: str,
    entry_signal_score: Decimal | None = None,
    trade_overrides: TradeOpenOverrides | None = None,
) -> Position:
    """Verilen sembol+yon icin gercek/simule pozisyon acar. Basarisizsa
    ``PositionOpenSkipped`` firlatir (bu bir HATA degildir, sadece islem
    atlanmistir); protective order basarisizligi gibi kritik durumlarda ise
    olusan hata dogrudan yukari firlatilir (loglanmasi ve admin'e
    bildirilmesi icin)."""

    if getattr(settings_row, "market_direction_filter_enabled", False):
        if not (trade_overrides and trade_overrides.bypass_market_direction_filter):
            from .market_regime import fetch_btc_market_regime, signal_allowed_for_regime

            regime = await fetch_btc_market_regime(adapter)
            if regime and not signal_allowed_for_regime(side, regime.direction):
                await _record_risk_event(
                    session,
                    "MARKET_DIRECTION_FILTER",
                    symbol_row.symbol,
                    "INFO",
                    f"BTC piyasa {regime.direction} → {side} acilmasi engellendi",
                    settings_row.mode,
                )
                raise PositionOpenSkipped("market_direction_filter_blocked")

    filters = build_symbol_filters(symbol_row)
    rule = await get_or_create_symbol_rule(session, settings_row.admin_id or "", symbol_row.symbol)
    requested_leverage = rule.max_leverage_override if (rule and rule.max_leverage_override) else settings_row.leverage
    requested_leverage = min(requested_leverage, settings_row.max_allowed_leverage)

    try:
        await adapter.change_margin_type(symbol_row.symbol, settings_row.margin_type)
    except Exception as exc:  # noqa: BLE001
        await _record_risk_event(
            session, "LEVERAGE_NOT_CONFIRMED", symbol_row.symbol, "ERROR",
            f"Marj tipi ayarlanamadi: {exc}", settings_row.mode,
        )
        raise PositionOpenSkipped("leverage_or_margin_type_setup_failed") from exc

    mark_tick = await adapter.get_mark_price(symbol_row.symbol)
    price = mark_tick.mark_price

    balances = await adapter.get_account_balance()
    usdt_balance = next((b for b in balances if b.asset == "USDT"), None)
    available_balance = usdt_balance.available_balance if usdt_balance else ZERO

    resolved = await _resolve_leverage_for_open(
        adapter,
        settings_row,
        symbol_row,
        side,
        price,
        filters,
        available_balance,
        requested_leverage,
    )
    if resolved is None:
        skip_reason = (
            "liquidation_distance_too_small"
            if getattr(settings_row, "risk_adjusted_leverage_enabled", False)
            else "position_sizing_failed"
        )
        if skip_reason == "liquidation_distance_too_small":
            await _record_risk_event(
                session, "LIQUIDATION_DISTANCE", symbol_row.symbol, "WARNING",
                f"Stop-loss likidasyona cok yakin (hedef kaldirac {requested_leverage}x)", settings_row.mode,
            )
        raise PositionOpenSkipped(skip_reason)

    leverage, sizing, stop_loss_price, take_profit_price, estimated_liquidation = resolved

    try:
        leverage_result = await adapter.change_leverage(symbol_row.symbol, leverage)
        if leverage_result.leverage != leverage:
            raise PositionOpenSkipped("leverage_not_confirmed")
    except PositionOpenSkipped:
        raise
    except Exception as exc:  # noqa: BLE001
        await _record_risk_event(
            session, "LEVERAGE_NOT_CONFIRMED", symbol_row.symbol, "ERROR",
            f"Kaldirac ayarlanamadi: {exc}", settings_row.mode,
        )
        raise PositionOpenSkipped("leverage_or_margin_type_setup_failed") from exc

    side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
    open_sl_roi = _exchange_sl_roi_pct(settings_row, loss_add_count=0)
    open_side = "BUY" if side == "LONG" else "SELL"
    open_client_id = generate_client_order_id("open")
    order_request = PlaceOrderRequest(
        symbol=symbol_row.symbol, side=open_side, quantity=sizing.quantity, client_order_id=open_client_id,
    )

    now = datetime.now(timezone.utc)
    order_row = Order(
        symbol=symbol_row.symbol, side=open_side, order_type="MARKET", purpose="OPEN",
        quantity=sizing.quantity, client_order_id=open_client_id, status="SUBMITTING", bot_mode=settings_row.mode,
        submitted_at=now,
    )
    session.add(order_row)
    await session.flush()

    exchange_order = await adapter.place_market_order(order_request)
    exchange_order = await _await_order_fill(
        session, adapter, settings_row, symbol_row, side, open_client_id, exchange_order, order_row,
        entry_signal_score,
    )

    entry_price = exchange_order.avg_price if exchange_order.avg_price > 0 else price
    filled_qty = exchange_order.executed_qty if exchange_order.executed_qty > ZERO else sizing.quantity

    order_row.status = exchange_order.status
    order_row.binance_order_id = exchange_order.binance_order_id
    order_row.avg_fill_price = entry_price
    order_row.filled_quantity = filled_qty
    order_row.filled_at = now if exchange_order.status == "FILLED" else None

    # Gercek dolum fiyatina gore SL/TP yeniden hesaplanir ve tickSize'a yuvarlanir.
    roi_result = compute_roi_prices(
        RoiPriceInputs(
            entry_price=entry_price,
            quantity=filled_qty,
            side=side_enum,
            leverage=Decimal(leverage),
            take_profit_roi_pct=settings_row.take_profit_roi_pct,
            stop_loss_roi_pct=open_sl_roi,
            taker_commission_rate=settings_row.paper_taker_commission_rate,
        )
    )
    stop_loss_price = _round_protective_trigger_price(filters, roi_result.stop_loss_price, side, "STOP_LOSS")
    take_profit_price = _round_protective_trigger_price(filters, roi_result.take_profit_price, side, "TAKE_PROFIT")

    open_commission = entry_price * filled_qty * settings_row.paper_taker_commission_rate
    notional = entry_price * filled_qty

    position = Position(
        symbol=symbol_row.symbol, side=side, status="OPEN", bot_mode=settings_row.mode,
        admin_id=settings_row.admin_id,
        margin_type=settings_row.margin_type, leverage=leverage, margin_usdt=settings_row.margin_per_trade_usdt,
        quantity=filled_qty, notional_usdt=notional, entry_price=entry_price, mark_price=entry_price,
        liquidation_price=estimated_liquidation, stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price, open_commission_usdt=open_commission,
        protective_orders_ok=False, signal_id=signal_id, open_reason=open_reason,
        loss_add_count=0,
        open_order_id=exchange_order.binance_order_id or open_client_id, opened_at=now,
    )
    session.add(position)
    await session.flush()
    order_row.position_id = position.id
    await session.commit()

    from shared.firestore.tenant_sync import sync_tenant_position_open

    await sync_tenant_position_open(settings_row.admin_id, position)

    from .config import get_worker_settings
    from .tenant_ops import send_position_opened_notification

    worker_settings = get_worker_settings()
    await send_position_opened_notification(
        session,
        worker_settings,
        settings_row.admin_id,
        symbol=symbol_row.symbol,
        side=side,
        entry_price=entry_price,
        quantity=filled_qty,
        margin_usdt=settings_row.margin_per_trade_usdt,
        leverage=leverage,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        bot_mode=settings_row.mode,
        open_reason=open_reason,
        position_id=position.id,
    )

    try:
        try:
            await adapter.cancel_all_open_orders(symbol_row.symbol)
        except Exception:  # noqa: BLE001
            pass
        sl_ok, sl_algo = await _place_protective_order(
            session, adapter, position, "STOP_LOSS", stop_loss_price, settings_row, filters
        )
        tp_ok, tp_algo = await _place_protective_order(
            session, adapter, position, "TAKE_PROFIT", take_profit_price, settings_row, filters
        )
    except Exception:
        await _emergency_close_unprotected(session, adapter, position, settings_row)
        raise

    sl_algo, tp_algo = await _finalize_protective_orders_or_emergency_close(
        session, adapter, position, settings_row, sl_ok, tp_ok, sl_algo, tp_algo
    )

    position.protective_orders_ok = True
    position.stop_loss_algo_order_id = sl_algo.client_algo_id
    position.take_profit_algo_order_id = tp_algo.client_algo_id
    await _record_bot_event(
        session, "POSITION_OPENED",
        f"{symbol_row.symbol} {side} pozisyon acildi (miktar={filled_qty}, giris={entry_price})",
        settings_row.mode,
        {"symbol": symbol_row.symbol, "side": side, "quantity": str(filled_qty), "entry_price": str(entry_price)},
    )
    runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
    runtime = runtime_result.scalar_one_or_none()
    if runtime is not None:
        runtime.last_order_at = now
    await session.commit()
    await session.refresh(position)
    return position


async def _place_protective_order(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    position: Position,
    purpose: str,
    trigger_price: Decimal,
    settings_row,
    filters: SymbolFilters,
) -> tuple[bool, AlgoOrder]:
    close_side = "SELL" if position.side == "LONG" else "BUY"
    order_type = "STOP_MARKET" if purpose == "STOP_LOSS" else "TAKE_PROFIT_MARKET"
    client_algo_id = generate_client_algo_id("sl" if purpose == "STOP_LOSS" else "tp")
    rounded_trigger = _round_protective_trigger_price(filters, trigger_price, position.side, purpose)

    algo_row = AlgoOrder(
        position_id=position.id, symbol=position.symbol, purpose=purpose, side=close_side, order_type=order_type,
        trigger_price=rounded_trigger, working_type=settings_row.working_type, close_position=True,
        client_algo_id=client_algo_id, status="SUBMITTING", bot_mode=settings_row.mode,
    )
    session.add(algo_row)
    await session.flush()

    last_exc: Exception | None = None
    for attempt in range(PROTECTIVE_ORDER_MAX_ATTEMPTS):
        request = PlaceAlgoOrderRequest(
            symbol=position.symbol, side=close_side, order_type=order_type, stop_price=rounded_trigger,
            client_algo_id=client_algo_id, working_type=settings_row.working_type,
        )
        try:
            if purpose == "STOP_LOSS":
                exchange_order = await adapter.place_stop_loss_order(request)
            else:
                exchange_order = await adapter.place_take_profit_order(request)
            algo_row.status = "NEW"
            algo_row.trigger_price = rounded_trigger
            algo_row.binance_order_id = exchange_order.binance_order_id
            await session.commit()
            return True, algo_row
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_duplicate_protective_order_error(exc):
                existing_ex = await _find_open_protective_algo(adapter, position.symbol, purpose)
                if existing_ex is not None:
                    attached = await _attach_existing_protective_algo(
                        session, position, purpose, existing_ex, settings_row, algo_row
                    )
                    logger.info(
                        "%s %s borsada zaten vardi, mevcut emir kullanildi",
                        position.symbol,
                        purpose,
                    )
                    await session.commit()
                    return True, attached
            logger.warning(
                "%s %s koruyucu emri basarisiz (%s/%s): %s",
                position.symbol, purpose, attempt + 1, PROTECTIVE_ORDER_MAX_ATTEMPTS, exc,
            )
            if attempt < PROTECTIVE_ORDER_MAX_ATTEMPTS - 1:
                await asyncio.sleep(PROTECTIVE_ORDER_RETRY_INTERVAL_SEC)
                # Precision hatasinda bir tick kaydirarak yeniden dene
                tick = filters.price_tick_size
                if position.side == "LONG":
                    rounded_trigger = rounded_trigger - tick if purpose == "STOP_LOSS" else rounded_trigger + tick
                else:
                    rounded_trigger = rounded_trigger + tick if purpose == "STOP_LOSS" else rounded_trigger - tick
                if rounded_trigger <= ZERO:
                    break
                algo_row.trigger_price = rounded_trigger
                continue
            break

    if _is_duplicate_protective_order_error(last_exc):
        existing_ex = await _find_open_protective_algo(adapter, position.symbol, purpose)
        if existing_ex is not None:
            attached = await _attach_existing_protective_algo(
                session, position, purpose, existing_ex, settings_row, algo_row
            )
            logger.info(
                "%s %s borsada zaten vardi, mevcut emir kullanildi",
                position.symbol,
                purpose,
            )
            await session.commit()
            return True, attached

    algo_row.status = "REJECTED"
    algo_row.last_error = str(last_exc)
    await _record_risk_event(
        session, "PROTECTIVE_ORDER_FAILED", position.symbol, "CRITICAL",
        f"{purpose} emri gonderilemedi: {last_exc}", settings_row.mode,
    )
    await session.commit()
    return False, algo_row


async def open_position_limit_entry(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    side: str,
    signal_id: str | None,
    open_reason: str,
    entry_signal_score: Decimal | None = None,
    trade_overrides: TradeOpenOverrides | None = None,
) -> Order:
    """Sinyal geldiginde market emri yerine GTC limit emir atar (olta modu).

    Limit fiyat:
      LONG  → mark_price × (1 - offset_pct / 100)  [piyasanin altina]
      SHORT → mark_price × (1 + offset_pct / 100)  [piyasanin ustune]

    Emir hemen gonderilir; dolum beklemeden ``Order`` nesnesi dondurulur.
    Tamamlanma/iptal izleme ``monitor_limit_entries()`` tarafindan yapilir.
    """
    from sqlalchemy import and_  # noqa: PLC0415

    # Ayni sembol icin zaten bekleyen limit emri varsa tekrar atma
    admin_id = settings_row.admin_id or ""
    existing_check = await session.execute(
        select(Order).where(
            and_(
                Order.admin_id == admin_id,
                Order.symbol == symbol_row.symbol,
                Order.order_type == "LIMIT",
                Order.purpose == "OPEN",
                Order.status.in_(["PENDING", "NEW", "SUBMITTING"]),
            )
        )
    )
    if existing_check.scalar_one_or_none() is not None:
        raise PositionOpenSkipped("limit_entry_already_pending")

    from shared.trading_risk import count_filled_open_positions, count_pending_limit_entry_orders

    pending_olta = await count_pending_limit_entry_orders(session, settings_row.mode, admin_id)
    max_pending = int(getattr(settings_row, "limit_entry_max_pending", 3) or 3)
    if pending_olta >= max_pending:
        raise PositionOpenSkipped("limit_entry_max_pending_reached")

    filled_open = await count_filled_open_positions(session, settings_row.mode, admin_id)
    if filled_open >= settings_row.max_open_positions:
        raise PositionOpenSkipped("max_open_positions_reached")
    filled_for_symbol = await count_filled_open_positions(session, settings_row.mode, admin_id, symbol=symbol_row.symbol)
    if filled_for_symbol >= settings_row.max_open_positions_per_symbol:
        raise PositionOpenSkipped("max_open_positions_per_symbol_reached")

    if getattr(settings_row, "market_direction_filter_enabled", False):
        if not (trade_overrides and trade_overrides.bypass_market_direction_filter):
            from .market_regime import fetch_btc_market_regime, signal_allowed_for_regime

            regime = await fetch_btc_market_regime(adapter)
            if regime and not signal_allowed_for_regime(side, regime.direction):
                raise PositionOpenSkipped("market_direction_filter_blocked")

    filters = build_symbol_filters(symbol_row)
    rule = await get_or_create_symbol_rule(session, settings_row.admin_id or "", symbol_row.symbol)
    leverage = rule.max_leverage_override if (rule and rule.max_leverage_override) else settings_row.leverage
    leverage = min(leverage, settings_row.max_allowed_leverage)

    try:
        leverage_result = await adapter.change_leverage(symbol_row.symbol, leverage)
        if leverage_result.leverage != leverage:
            raise PositionOpenSkipped("leverage_not_confirmed")
        await adapter.change_margin_type(symbol_row.symbol, settings_row.margin_type)
    except PositionOpenSkipped:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PositionOpenSkipped("leverage_or_margin_type_setup_failed") from exc

    mark_tick = await adapter.get_mark_price(symbol_row.symbol)
    mark_price = mark_tick.mark_price
    offset = Decimal(str(settings_row.limit_entry_offset_pct)) / 100

    if side == "LONG":
        raw_limit = mark_price * (1 - offset)
        limit_price = quantize_price(raw_limit, filters.price_tick_size, rounding=ROUND_DOWN)
    else:
        raw_limit = mark_price * (1 + offset)
        limit_price = quantize_price(raw_limit, filters.price_tick_size, rounding=ROUND_UP)

    balances = await adapter.get_account_balance()
    usdt_balance = next((b for b in balances if b.asset == "USDT"), None)
    available_balance = usdt_balance.available_balance if usdt_balance else ZERO

    sizing = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=settings_row.margin_per_trade_usdt,
            leverage=Decimal(leverage),
            price=limit_price,
            filters=filters,
            available_balance_usdt=available_balance,
        )
    )
    if not sizing.ok:
        raise PositionOpenSkipped(sizing.reason or "position_sizing_failed")

    open_side = "BUY" if side == "LONG" else "SELL"
    open_client_id = generate_client_order_id("olta")
    now = datetime.now(timezone.utc)

    order_row = Order(
        symbol=symbol_row.symbol, side=open_side, order_type="LIMIT", purpose="OPEN",
        quantity=sizing.quantity, price=limit_price, client_order_id=open_client_id,
        status="PENDING", bot_mode=settings_row.mode, submitted_at=now,
    )
    session.add(order_row)

    request = PlaceOrderRequest(
        symbol=symbol_row.symbol, side=open_side, quantity=sizing.quantity,
        client_order_id=open_client_id, price=limit_price,
    )
    try:
        exchange_order = await adapter.place_limit_order(request)
        order_row.status = exchange_order.status if exchange_order.status != "FILLED" else "PENDING"
        order_row.binance_order_id = exchange_order.binance_order_id
        if exchange_order.status == "FILLED":
            order_row.status = "FILLED"
            order_row.avg_fill_price = exchange_order.avg_price
            order_row.filled_quantity = exchange_order.executed_qty
            order_row.filled_at = now
    except Exception as exc:  # noqa: BLE001
        order_row.status = "FAILED"
        order_row.last_error = str(exc)[:512]
        await session.commit()
        raise PositionOpenSkipped("limit_order_placement_failed") from exc

    await session.commit()
    await session.refresh(order_row)

    await _record_bot_event(
        session, "LIMIT_ENTRY_PLACED",
        f"{symbol_row.symbol} {side} olta emri verildi (limit={limit_price}, mark={mark_price}, offset={settings_row.limit_entry_offset_pct}%)",
        settings_row.mode,
        {"symbol": symbol_row.symbol, "side": side, "limit_price": str(limit_price), "mark_price": str(mark_price)},
    )
    runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
    runtime = runtime_result.scalar_one_or_none()
    if runtime is not None:
        runtime.last_order_at = now
    await session.commit()
    logger.info(
        "Olta emri verildi: %s %s | limit=%s | mark=%s | miktar=%s",
        symbol_row.symbol, side, limit_price, mark_price, sizing.quantity,
    )

    # Paper modda emir aninda doldu → pozisyonu hemen tamamla
    if order_row.status == "FILLED":
        await _complete_limit_entry_fill(session, adapter, settings_row, symbol_row, order_row, side, leverage, signal_id, open_reason)

    return order_row


async def _complete_limit_entry_fill(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    order_row: Order,
    side: str,
    leverage: int,
    signal_id: str | None,
    open_reason: str,
) -> Position:
    """Dolmus bir olta emrinden pozisyon olusturur ve SL/TP emirlerini yerlestirir."""
    filters = build_symbol_filters(symbol_row)
    side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
    entry_price = order_row.avg_fill_price or order_row.price or ZERO
    filled_qty = order_row.filled_quantity or order_row.quantity
    now = datetime.now(timezone.utc)

    maint_margin_rate = await _pick_maintenance_margin_rate(adapter, symbol_row.symbol, entry_price * filled_qty)
    estimated_liquidation = estimate_liquidation_price(entry_price, Decimal(leverage), side_enum, maint_margin_rate)

    roi_result = compute_roi_prices(
        RoiPriceInputs(
            entry_price=entry_price,
            quantity=filled_qty,
            side=side_enum,
            leverage=Decimal(leverage),
            take_profit_roi_pct=settings_row.take_profit_roi_pct,
            stop_loss_roi_pct=settings_row.stop_loss_roi_pct,
            taker_commission_rate=settings_row.paper_taker_commission_rate,
        )
    )
    stop_loss_price = _round_protective_trigger_price(filters, roi_result.stop_loss_price, side, "STOP_LOSS")
    take_profit_price = _round_protective_trigger_price(filters, roi_result.take_profit_price, side, "TAKE_PROFIT")

    distance_pct = liquidation_distance_pct(stop_loss_price, estimated_liquidation, side_enum)
    liq_check = check_liquidation_distance(distance_pct, settings_row.min_liquidation_distance_pct)
    if not liq_check.ok:
        await _record_risk_event(
            session, "LIQUIDATION_DISTANCE", symbol_row.symbol, "WARNING",
            f"Olta dolum: stop-loss likidasyona cok yakin (mesafe %{distance_pct:.2f})", settings_row.mode,
        )

    open_commission = entry_price * filled_qty * settings_row.paper_taker_commission_rate
    notional = entry_price * filled_qty

    position = Position(
        symbol=symbol_row.symbol, side=side, status="OPEN", bot_mode=settings_row.mode,
        admin_id=settings_row.admin_id,
        margin_type=settings_row.margin_type, leverage=leverage, margin_usdt=settings_row.margin_per_trade_usdt,
        quantity=filled_qty, notional_usdt=notional, entry_price=entry_price, mark_price=entry_price,
        liquidation_price=estimated_liquidation, stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price, open_commission_usdt=open_commission,
        protective_orders_ok=False, signal_id=signal_id, open_reason=open_reason,
        open_order_id=order_row.binance_order_id or order_row.client_order_id, opened_at=now,
    )
    session.add(position)
    await session.flush()
    order_row.position_id = position.id
    await session.commit()

    from shared.firestore.tenant_sync import sync_tenant_position_open

    await sync_tenant_position_open(settings_row.admin_id, position)

    from .config import get_worker_settings
    from .tenant_ops import send_position_opened_notification

    worker_settings = get_worker_settings()
    await send_position_opened_notification(
        session,
        worker_settings,
        settings_row.admin_id,
        symbol=symbol_row.symbol,
        side=side,
        entry_price=entry_price,
        quantity=filled_qty,
        margin_usdt=settings_row.margin_per_trade_usdt,
        leverage=leverage,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        bot_mode=settings_row.mode,
        open_reason=open_reason or "OLTA_LIMIT",
        position_id=position.id,
    )

    try:
        try:
            await adapter.cancel_all_open_orders(symbol_row.symbol)
        except Exception:  # noqa: BLE001
            pass
        sl_ok, sl_algo = await _place_protective_order(
            session, adapter, position, "STOP_LOSS", stop_loss_price, settings_row, filters
        )
        tp_ok, tp_algo = await _place_protective_order(
            session, adapter, position, "TAKE_PROFIT", take_profit_price, settings_row, filters
        )
    except Exception:
        await _emergency_close_unprotected(session, adapter, position, settings_row)
        raise

    sl_algo, tp_algo = await _finalize_protective_orders_or_emergency_close(
        session, adapter, position, settings_row, sl_ok, tp_ok, sl_algo, tp_algo
    )

    position.protective_orders_ok = True
    position.stop_loss_algo_order_id = sl_algo.client_algo_id
    position.take_profit_algo_order_id = tp_algo.client_algo_id
    await _record_bot_event(
        session, "POSITION_OPENED",
        f"{symbol_row.symbol} {side} olta pozisyonu acildi (miktar={filled_qty}, giris={entry_price})",
        settings_row.mode,
        {"symbol": symbol_row.symbol, "side": side, "quantity": str(filled_qty), "entry_price": str(entry_price)},
    )

    runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
    runtime = runtime_result.scalar_one_or_none()
    if runtime is not None:
        runtime.last_order_at = now
    await session.commit()
    await session.refresh(position)
    return position


async def monitor_limit_entries(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
) -> None:
    """Bekleyen olta emirlerini izler: dolumu tamamlar, zaman asimlarini iptal eder.

    Bu fonksiyon her 30 saniyede bir cagrilmalidir (bkz. main.py olta_monitor_loop).
    """
    from sqlalchemy import and_  # noqa: PLC0415 (geciktirilmis import, dongusel bagimlilik onlenir)

    pending_result = await session.execute(
        select(Order).where(
            and_(
                Order.order_type == "LIMIT",
                Order.purpose == "OPEN",
                Order.status.in_(["PENDING", "NEW"]),
            )
        )
    )
    pending_orders: list[Order] = list(pending_result.scalars().all())

    if not pending_orders:
        return

    timeout_minutes = int(settings_row.limit_entry_timeout_minutes)

    for order_row in pending_orders:
        try:
            await _process_single_limit_entry(session, adapter, settings_row, order_row, timeout_minutes)
        except Exception:  # noqa: BLE001
            logger.exception("Olta emri izleme hatasi (client_id=%s)", order_row.client_order_id)


async def _process_single_limit_entry(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    order_row: Order,
    timeout_minutes: int,
) -> None:
    """Tek bir bekleyen olta emrini kontrol eder ve gerekirse islem yapar."""
    from sqlalchemy import select as sa_select  # noqa: PLC0415
    now = datetime.now(timezone.utc)

    # Zaman asimi kontrolu
    if order_row.submitted_at is not None:
        submitted_at = order_row.submitted_at
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = (now - submitted_at).total_seconds() / 60
        if elapsed_minutes >= timeout_minutes:
            logger.info("Olta emri zaman asimi → iptal ediliyor: %s", order_row.client_order_id)
            try:
                await adapter.cancel_order(order_row.symbol, order_row.client_order_id)
            except Exception:  # noqa: BLE001
                pass
            order_row.status = "CANCELED"
            order_row.canceled_at = now
            order_row.last_error = f"zaman_asimi_{timeout_minutes}dk"
            await session.commit()
            return

    # Binance'tan guncel durum sorgula
    exchange_order = await adapter.query_order(order_row.symbol, order_row.client_order_id)
    if exchange_order is None:
        logger.warning("Olta emri Binance'ta bulunamadi: %s", order_row.client_order_id)
        order_row.status = "CANCELED"
        order_row.canceled_at = now
        await session.commit()
        return

    if exchange_order.status in ("CANCELED", "REJECTED", "EXPIRED"):
        order_row.status = "CANCELED"
        order_row.canceled_at = now
        await session.commit()
        return

    if exchange_order.status == "FILLED" and exchange_order.executed_qty > ZERO:
        logger.info("Olta emri doldu → pozisyon aciliyor: %s", order_row.client_order_id)
        order_row.status = "FILLED"
        order_row.avg_fill_price = exchange_order.avg_price
        order_row.filled_quantity = exchange_order.executed_qty
        order_row.filled_at = now
        await session.flush()

        # Symbol bilgisi yukle
        symbol_result = await session.execute(
            sa_select(Symbol).where(Symbol.symbol == order_row.symbol)
        )
        symbol_row = symbol_result.scalar_one_or_none()
        if symbol_row is None:
            logger.error("Olta dolumu: sembol bulunamadi %s", order_row.symbol)
            await session.commit()
            return

        rule = await get_or_create_symbol_rule(session, settings_row.admin_id or "", order_row.symbol)
        leverage = rule.max_leverage_override if (rule and rule.max_leverage_override) else settings_row.leverage
        leverage = min(leverage, settings_row.max_allowed_leverage)

        side = "LONG" if order_row.side == "BUY" else "SHORT"
        await _complete_limit_entry_fill(
            session, adapter, settings_row, symbol_row, order_row, side, leverage,
            signal_id=None, open_reason="limit_entry_filled",
        )
        return

    # Emir hala bekliyor → signal skoru kontrol et
    # (skoru dusen sinyallerde emri iptal et)
    symbol_result = await session.execute(
        sa_select(Symbol).where(Symbol.symbol == order_row.symbol)
    )
    symbol_row = symbol_result.scalar_one_or_none()
    if symbol_row is not None:
        try:
            expected_side = "LONG" if order_row.side == "BUY" else "SHORT"
            should_cancel, cancel_reason = await _limit_entry_should_cancel(
                session, adapter, settings_row, symbol_row, expected_side
            )
            if should_cancel:
                logger.info(
                    "Olta emri: %s → iptal (%s %s)",
                    cancel_reason or "sinyal_gecersiz",
                    order_row.symbol,
                    expected_side,
                )
                try:
                    await adapter.cancel_order(order_row.symbol, order_row.client_order_id)
                except Exception:  # noqa: BLE001
                    pass
                order_row.status = "CANCELED"
                order_row.canceled_at = now
                order_row.last_error = cancel_reason or "sinyal_gecersiz"
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.warning("Olta sinyal kontrolu basarisiz, emir beklemede kaliyor: %s", order_row.client_order_id)


async def _limit_entry_should_cancel(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row,
    symbol_row: Symbol,
    expected_side: str,
) -> tuple[bool, str | None]:
    """Olta emri beklerken iptal gerekip gerekmedigini kontrol eder.

    Sinyal gecici olarak ``suggested_side=None`` olsa bile (skor hala yuksekse)
    emri acik birakir; yalnizca yon tersine donerse veya skor ciddi duserse iptal eder.
    """

    live_result = await evaluate_live_signal_score(session, adapter, settings_row, symbol_row)
    if live_result is None:
        return False, None
    if live_result.suggested_side is not None and live_result.suggested_side != expected_side:
        min_score = float(settings_row.min_signal_score)
        if live_result.breakdown.total_score >= min_score:
            return True, "signal_side_changed"
        return False, None
    min_score = float(settings_row.min_signal_score)
    buffer = 5.0
    if live_result.breakdown.total_score < min_score - buffer:
        return True, "signal_score_dropped"
    return False, None


async def _emergency_close_unprotected(
    session: AsyncSession, adapter: BinanceFuturesAdapter, position: Position, settings_row
) -> None:
    """SL/TP yerlesemedigi icin acik kalan korumasiz pozisyonu ACILEN kapatir."""

    sl_on_ex, tp_on_ex = await _exchange_has_both_protective_orders(adapter, position.symbol)
    if sl_on_ex and tp_on_ex:
        recovered, _, _ = await _try_recover_protective_orders_on_exchange(
            session, adapter, position, settings_row
        )
        if recovered:
            await session.commit()
            logger.warning(
                "Korumasiz sanildi ama borsada SL+TP mevcut, acil kapatma iptal: %s",
                position.symbol,
            )
            return

    logger.critical("Korumasiz pozisyon tespit edildi, acilen kapatiliyor: %s", position.symbol)
    close_side = "SELL" if position.side == "LONG" else "BUY"
    try:
        close_request = PlaceOrderRequest(
            symbol=position.symbol, side=close_side, quantity=position.quantity,
            client_order_id=generate_client_order_id("emrg"), reduce_only=True,
        )
        exchange_order = await adapter.place_reduce_only_market_order(close_request)
        exit_price = exchange_order.avg_price if exchange_order.avg_price > 0 else position.entry_price
    except Exception as exc:  # noqa: BLE001
        # Kapanis emri de basarisiz oldu: bu EN KRITIK durumdur, admin'e bildirilmelidir.
        position.status = "OPEN"
        await _record_risk_event(
            session, "PROTECTIVE_ORDER_FAILED", position.symbol, "CRITICAL",
            f"KRITIK: korumasiz pozisyon kapatilamiyor! Manuel mudahale gerekli: {exc}", settings_row.mode,
        )
        runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
        runtime = runtime_result.scalar_one_or_none()
        if runtime is not None:
            runtime.run_state = "SAFE_MODE"
            runtime.safe_mode_reason = f"{position.symbol} korumasiz pozisyon kapatilamadi, manuel mudahale gerekli"
        await session.commit()
        raise

    position.status = "CLOSED"
    position.exit_price = exit_price
    position.close_reason = "EMERGENCY_STOP"
    position.closed_at = datetime.now(timezone.utc)
    side_enum = PositionSide.LONG if position.side == "LONG" else PositionSide.SHORT
    gross_pnl = compute_realized_pnl(position.entry_price, exit_price, position.quantity, side_enum)
    close_commission = position.quantity * exit_price * Decimal("0.0004")
    net_pnl = gross_pnl - position.open_commission_usdt - close_commission - position.funding_fee_usdt
    margin = position.margin_usdt
    net_roi = (net_pnl / margin * 100) if margin else Decimal("0")
    await _record_bot_event(
        session, "POSITION_CLOSED", f"{position.symbol} korumasiz pozisyon acilen kapatildi", settings_row.mode,
    )
    await session.commit()
    try:
        from .config import get_worker_settings
        from .tenant_ops import send_position_closed_notification

        worker_settings = get_worker_settings()
        await send_position_closed_notification(
            session,
            worker_settings,
            settings_row.admin_id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            net_pnl_usdt=net_pnl,
            net_roi_pct=net_roi,
            close_reason="EMERGENCY_STOP",
            bot_mode=settings_row.mode,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
            position_id=position.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram acil kapanis bildirimi gonderilemedi: %s", exc)

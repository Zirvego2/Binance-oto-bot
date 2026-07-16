"""Piyasa genel gorunumu — breadth, alim/satim baskisi, BTC ozeti."""

from __future__ import annotations

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings
from shared.market_breadth import MarketBreadthSnapshot, compute_market_breadth

from ..core.binance_client import get_binance_adapter
from ..core.config import Settings
from ..schemas.market import (
    BtcQuickOut,
    MarketOverviewOut,
    OrderBookPressureOut,
    TickerMoverOut,
)
from .market_helpers import fetch_market_regime_out

CACHE_KEY = "market:overview:v1"
CACHE_TTL_SEC = 20
BTC_SYMBOL = "BTCUSDT"


def _mover_out(m) -> TickerMoverOut:
    return TickerMoverOut(
        symbol=m.symbol,
        last_price=m.last_price,
        change_pct=m.change_pct,
        quote_volume_usdt=m.quote_volume_usdt,
    )


def _snapshot_to_out(
    snap: MarketBreadthSnapshot,
    *,
    btc: BtcQuickOut,
    order_book: OrderBookPressureOut | None,
    bot_regime_direction: str | None,
    market_direction_filter_enabled: bool,
) -> MarketOverviewOut:
    return MarketOverviewOut(
        analyzed_at=snap.analyzed_at,
        universe_count=snap.universe_count,
        rising_count=snap.rising_count,
        falling_count=snap.falling_count,
        flat_count=snap.flat_count,
        rising_pct=snap.rising_pct,
        falling_pct=snap.falling_pct,
        flat_pct=snap.flat_pct,
        sentiment=snap.sentiment,
        sentiment_score=snap.sentiment_score,
        buy_pressure_pct=snap.buy_pressure_pct,
        sell_pressure_pct=snap.sell_pressure_pct,
        avg_change_pct=snap.avg_change_pct,
        median_change_pct=snap.median_change_pct,
        total_volume_24h_usdt=snap.total_volume_24h_usdt,
        btc=btc,
        order_book_pressure=order_book,
        bot_regime_direction=bot_regime_direction,
        market_direction_filter_enabled=market_direction_filter_enabled,
        top_gainers=[_mover_out(m) for m in snap.top_gainers],
        top_losers=[_mover_out(m) for m in snap.top_losers],
        top_volume=[_mover_out(m) for m in snap.top_volume],
    )


async def fetch_market_overview(
    session: AsyncSession,
    app_settings: Settings,
    redis: Redis | None = None,
    *,
    force_refresh: bool = False,
) -> MarketOverviewOut:
    if redis and not force_refresh:
        cached = await redis.get(CACHE_KEY)
        if cached:
            return MarketOverviewOut.model_validate_json(cached)

    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings_row = settings_result.scalar_one_or_none()
    mode = settings_row.mode if settings_row else app_settings.binance_env
    market_direction_filter_enabled = bool(
        getattr(settings_row, "market_direction_filter_enabled", False) if settings_row else False
    )

    adapter = get_binance_adapter(mode)
    try:
        tickers = await adapter.get_24h_tickers()
        book = await adapter.get_book_ticker(BTC_SYMBOL)
        mark = await adapter.get_mark_price(BTC_SYMBOL)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Piyasa verisi alinamadi: {exc}") from exc

    snap = compute_market_breadth(tickers)

    btc_ticker = next((t for t in tickers if t.symbol == BTC_SYMBOL), None)
    btc = BtcQuickOut(
        symbol=BTC_SYMBOL,
        last_price=float(btc_ticker.last_price) if btc_ticker else float(mark.mark_price),
        change_24h_pct=float(btc_ticker.price_change_percent) if btc_ticker else 0.0,
        mark_price=float(mark.mark_price),
        funding_rate_pct=float(mark.funding_rate * 100),
        quote_volume_24h_usdt=float(btc_ticker.quote_volume) if btc_ticker else 0.0,
    )

    bid_qty = float(book.bid_qty)
    ask_qty = float(book.ask_qty)
    total_qty = bid_qty + ask_qty
    if total_qty > 0:
        bid_pct = round(bid_qty / total_qty * 100, 2)
        ask_pct = round(ask_qty / total_qty * 100, 2)
        if bid_pct - ask_pct >= 5:
            ob_bias = "BUY"
        elif ask_pct - bid_pct >= 5:
            ob_bias = "SELL"
        else:
            ob_bias = "NEUTRAL"
        order_book = OrderBookPressureOut(
            symbol=BTC_SYMBOL,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
            bid_pct=bid_pct,
            ask_pct=ask_pct,
            bias=ob_bias,
        )
    else:
        order_book = None

    try:
        regime = await fetch_market_regime_out(session, app_settings)
        bot_regime_direction = regime.direction
    except HTTPException:
        bot_regime_direction = None

    out = _snapshot_to_out(
        snap,
        btc=btc,
        order_book=order_book,
        bot_regime_direction=bot_regime_direction,
        market_direction_filter_enabled=market_direction_filter_enabled,
    )

    if redis:
        await redis.setex(CACHE_KEY, CACHE_TTL_SEC, out.model_dump_json())

    return out

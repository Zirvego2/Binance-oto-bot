"""Market regime fetch helper — route ve servisler tarafindan paylasilir."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings
from shared.market_regime import analyze_btc_market_regime

from ..core.binance_client import get_binance_adapter
from ..core.config import Settings
from ..schemas.market import MarketRegimeOut, TimeframeAnalysisOut

BTC_SYMBOL = "BTCUSDT"
PRIMARY_INTERVAL = "5m"
CONFIRM_INTERVAL = "15m"
KLINE_LIMIT = 120


def regime_to_out(result) -> MarketRegimeOut:
    return MarketRegimeOut(
        symbol=result.symbol,
        direction=result.direction,
        confidence=result.confidence,
        btc_price=result.btc_price,
        change_1h_pct=result.change_1h_pct,
        change_4h_pct=result.change_4h_pct,
        primary=TimeframeAnalysisOut(
            interval=result.primary.interval,
            price=result.primary.price,
            ema_fast=round(result.primary.ema_fast, 2),
            ema_mid=round(result.primary.ema_mid, 2),
            ema_slow=round(result.primary.ema_slow, 2),
            rsi=round(result.primary.rsi, 1),
            change_1h_pct=round(result.primary.change_1h_pct, 3),
            change_4h_pct=round(result.primary.change_4h_pct, 3),
            trend=result.primary.trend,
            momentum=result.primary.momentum,
        ),
        confirm=TimeframeAnalysisOut(
            interval=result.confirm.interval,
            price=result.confirm.price,
            ema_fast=round(result.confirm.ema_fast, 2),
            ema_mid=round(result.confirm.ema_mid, 2),
            ema_slow=round(result.confirm.ema_slow, 2),
            rsi=round(result.confirm.rsi, 1),
            change_1h_pct=round(result.confirm.change_1h_pct, 3),
            change_4h_pct=round(result.confirm.change_4h_pct, 3),
            trend=result.confirm.trend,
            momentum=result.confirm.momentum,
        ),
        long_score=result.long_score,
        short_score=result.short_score,
        reason=result.reason,
        recommendation=result.recommendation,
        components=result.components,
        analyzed_at=result.analyzed_at,
        primary_interval=PRIMARY_INTERVAL,
        confirm_interval=CONFIRM_INTERVAL,
    )


async def fetch_market_regime_out(session: AsyncSession, app_settings: Settings) -> MarketRegimeOut:
    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings_row = settings_result.scalar_one_or_none()
    mode = settings_row.mode if settings_row else app_settings.binance_env

    adapter = get_binance_adapter(mode)
    try:
        klines_5m = await adapter.get_klines(BTC_SYMBOL, PRIMARY_INTERVAL, limit=KLINE_LIMIT)
        klines_15m = await adapter.get_klines(BTC_SYMBOL, CONFIRM_INTERVAL, limit=KLINE_LIMIT)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BTC piyasa verisi alinamadi: {exc}") from exc

    result = analyze_btc_market_regime(
        klines_5m, klines_15m, symbol=BTC_SYMBOL,
        primary_interval=PRIMARY_INTERVAL, confirm_interval=CONFIRM_INTERVAL,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Piyasa analizi icin yeterli BTC verisi yok")
    return regime_to_out(result)

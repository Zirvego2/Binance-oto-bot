"""Worker icin BTC piyasa yonu okuma."""

from __future__ import annotations

import logging

from shared.binance.interface import BinanceFuturesAdapter
from shared.market_regime import MarketRegimeResult, analyze_btc_market_regime

logger = logging.getLogger("worker.market_regime")

BTC_SYMBOL = "BTCUSDT"


async def fetch_btc_market_regime(adapter: BinanceFuturesAdapter) -> MarketRegimeResult | None:
    try:
        klines_5m = await adapter.get_klines(BTC_SYMBOL, "5m", limit=120)
        klines_15m = await adapter.get_klines(BTC_SYMBOL, "15m", limit=120)
        return analyze_btc_market_regime(klines_5m, klines_15m, symbol=BTC_SYMBOL)
    except Exception:  # noqa: BLE001
        logger.warning("BTC piyasa yonu alinamadi", exc_info=True)
        return None


def signal_allowed_for_regime(suggested_side: str, market_direction: str) -> bool:
    """NEUTRAL iken her iki yon de acilabilir."""
    if market_direction == "NEUTRAL":
        return True
    if market_direction == "LONG" and suggested_side == "SHORT":
        return False
    if market_direction == "SHORT" and suggested_side == "LONG":
        return False
    return True


def select_best_signal_for_regime(
    candidates: list[tuple[object, object]],
    *,
    filter_enabled: bool,
    market_direction: str | None,
) -> tuple[object, object] | None:
    """Piyasa yonu filtresine uygun en yuksek skorlu sinyali secer."""
    best: tuple[object, object] | None = None
    for symbol_row, signal_result in candidates:
        side = getattr(signal_result, "suggested_side", None)
        if not side:
            continue
        if filter_enabled and market_direction and not signal_allowed_for_regime(side, market_direction):
            continue
        score = float(signal_result.breakdown.total_score)
        if best is None or score > float(best[1].breakdown.total_score):
            best = (symbol_row, signal_result)
    return best

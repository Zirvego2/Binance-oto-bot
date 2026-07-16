"""BTC kisa vadeli impuls tespiti."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from shared.binance.interface import BinanceFuturesAdapter

BTC_SYMBOL = "BTCUSDT"


@dataclass(frozen=True, slots=True)
class BtcImpulse:
    direction: str  # PUMP | DUMP | NONE
    change_pct: float
    lookback_minutes: int
    start_price: float
    end_price: float


async def detect_btc_impulse(
    adapter: BinanceFuturesAdapter,
    *,
    min_change_pct: float,
    lookback_minutes: int,
) -> BtcImpulse:
    limit = max(lookback_minutes + 5, 10)
    klines = await adapter.get_klines(BTC_SYMBOL, "1m", limit=limit)
    if len(klines) < lookback_minutes + 1:
        return BtcImpulse("NONE", 0.0, lookback_minutes, 0.0, 0.0)

    closes = [float(k.close) for k in klines]
    end_price = closes[-1]
    start_idx = max(0, len(closes) - lookback_minutes - 1)
    start_price = closes[start_idx]
    if start_price <= 0:
        return BtcImpulse("NONE", 0.0, lookback_minutes, start_price, end_price)

    change_pct = ((end_price - start_price) / start_price) * 100.0
    if change_pct >= min_change_pct:
        direction = "PUMP"
    elif change_pct <= -min_change_pct:
        direction = "DUMP"
    else:
        direction = "NONE"

    return BtcImpulse(direction, change_pct, lookback_minutes, start_price, end_price)


def impulse_to_counter_side(direction: str) -> str | None:
    if direction == "PUMP":
        return "SHORT"
    if direction == "DUMP":
        return "LONG"
    return None

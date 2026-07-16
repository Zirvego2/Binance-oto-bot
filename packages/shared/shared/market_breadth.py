"""USDS-M futures piyasa genisligi (breadth) ve alim/satim baskisi hesaplari."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .binance.types import Ticker24h

FLAT_THRESHOLD = Decimal("0.05")


@dataclass(frozen=True, slots=True)
class TickerMover:
    symbol: str
    last_price: float
    change_pct: float
    quote_volume_usdt: float


@dataclass(frozen=True, slots=True)
class MarketBreadthSnapshot:
    analyzed_at: datetime
    universe_count: int
    rising_count: int
    falling_count: int
    flat_count: int
    rising_pct: float
    falling_pct: float
    flat_pct: float
    sentiment: str
    sentiment_score: float
    buy_pressure_pct: float
    sell_pressure_pct: float
    avg_change_pct: float
    median_change_pct: float
    total_volume_24h_usdt: float
    top_gainers: list[TickerMover]
    top_losers: list[TickerMover]
    top_volume: list[TickerMover]


def _is_usdt_perpetual(symbol: str) -> bool:
    return symbol.endswith("USDT") and not symbol.endswith("USDCUSDT")


def _to_float(value: Decimal | float | int) -> float:
    return float(value)


def _ticker_mover(t: Ticker24h) -> TickerMover:
    return TickerMover(
        symbol=t.symbol,
        last_price=_to_float(t.last_price),
        change_pct=_to_float(t.price_change_percent),
        quote_volume_usdt=_to_float(t.quote_volume),
    )


def compute_market_breadth(
    tickers: list[Ticker24h],
    *,
    top_n: int = 10,
    flat_threshold: Decimal = FLAT_THRESHOLD,
) -> MarketBreadthSnapshot:
    """24 saatlik ticker listesinden piyasa genisligi ve baskı metrikleri."""
    filtered = [t for t in tickers if _is_usdt_perpetual(t.symbol)]
    if not filtered:
        now = datetime.now(UTC)
        return MarketBreadthSnapshot(
            analyzed_at=now,
            universe_count=0,
            rising_count=0,
            falling_count=0,
            flat_count=0,
            rising_pct=0.0,
            falling_pct=0.0,
            flat_pct=0.0,
            sentiment="NEUTRAL",
            sentiment_score=0.0,
            buy_pressure_pct=50.0,
            sell_pressure_pct=50.0,
            avg_change_pct=0.0,
            median_change_pct=0.0,
            total_volume_24h_usdt=0.0,
            top_gainers=[],
            top_losers=[],
            top_volume=[],
        )

    rising = falling = flat = 0
    changes: list[float] = []
    buy_vol = sell_vol = Decimal("0")
    total_vol = Decimal("0")

    for t in filtered:
        pct = t.price_change_percent
        vol = t.quote_volume
        total_vol += vol
        changes.append(_to_float(pct))

        if pct > flat_threshold:
            rising += 1
            buy_vol += vol
        elif pct < -flat_threshold:
            falling += 1
            sell_vol += vol
        else:
            flat += 1

    n = len(filtered)
    rising_pct = round(rising / n * 100, 2)
    falling_pct = round(falling / n * 100, 2)
    flat_pct = round(flat / n * 100, 2)

    if total_vol > 0:
        buy_pressure = float(buy_vol / total_vol * 100)
        sell_pressure = float(sell_vol / total_vol * 100)
    else:
        buy_pressure = sell_pressure = 50.0

    avg_change = round(sum(changes) / n, 3)
    sorted_changes = sorted(changes)
    mid = n // 2
    median_change = round(
        sorted_changes[mid] if n % 2 else (sorted_changes[mid - 1] + sorted_changes[mid]) / 2,
        3,
    )

    # Coin sayisi + hacim agirlikli baskı birlestirmesi (-100 .. +100)
    breadth_score = rising_pct - falling_pct
    volume_score = buy_pressure - sell_pressure
    sentiment_score = round(max(-100.0, min(100.0, breadth_score * 0.55 + volume_score * 0.45)), 1)

    if sentiment_score >= 15:
        sentiment = "BULLISH"
    elif sentiment_score <= -15:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    movers = [_ticker_mover(t) for t in filtered]
    by_change_desc = sorted(movers, key=lambda m: m.change_pct, reverse=True)
    by_volume = sorted(movers, key=lambda m: m.quote_volume_usdt, reverse=True)

    return MarketBreadthSnapshot(
        analyzed_at=datetime.now(UTC),
        universe_count=n,
        rising_count=rising,
        falling_count=falling,
        flat_count=flat,
        rising_pct=rising_pct,
        falling_pct=falling_pct,
        flat_pct=flat_pct,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        buy_pressure_pct=round(buy_pressure, 2),
        sell_pressure_pct=round(sell_pressure, 2),
        avg_change_pct=avg_change,
        median_change_pct=median_change,
        total_volume_24h_usdt=round(_to_float(total_vol), 2),
        top_gainers=by_change_desc[:top_n],
        top_losers=sorted(movers, key=lambda m: m.change_pct)[:top_n],
        top_volume=by_volume[:top_n],
    )

"""Unit tests for market breadth computation."""

from decimal import Decimal

from shared.binance.types import Ticker24h
from shared.market_breadth import compute_market_breadth


def _t(symbol: str, pct: str, vol: str) -> Ticker24h:
    return Ticker24h(
        symbol=symbol,
        price_change_percent=Decimal(pct),
        quote_volume=Decimal(vol),
        last_price=Decimal("1"),
    )


def test_compute_market_breadth_bullish():
    tickers = [
        _t("BTCUSDT", "2", "1000"),
        _t("ETHUSDT", "3", "800"),
        _t("SOLUSDT", "-1", "200"),
        _t("XRPUSDT", "0", "100"),
        _t("DOGEUSDT", "5", "500"),
    ]
    snap = compute_market_breadth(tickers, top_n=3)

    assert snap.universe_count == 5
    assert snap.rising_count == 3
    assert snap.falling_count == 1
    assert snap.flat_count == 1
    assert snap.sentiment == "BULLISH"
    assert snap.sentiment_score > 0
    assert len(snap.top_gainers) == 3
    assert snap.top_gainers[0].symbol == "DOGEUSDT"


def test_compute_market_breadth_bearish():
    tickers = [
        _t("BTCUSDT", "-4", "900"),
        _t("ETHUSDT", "-2", "700"),
        _t("SOLUSDT", "-6", "600"),
        _t("XRPUSDT", "1", "50"),
    ]
    snap = compute_market_breadth(tickers)

    assert snap.sentiment == "BEARISH"
    assert snap.falling_count == 3
    assert snap.buy_pressure_pct < snap.sell_pressure_pct


def test_ignores_non_usdt_perpetual():
    tickers = [
        _t("BTCUSDT", "2", "100"),
        _t("ETHBUSD", "10", "9999"),
    ]
    snap = compute_market_breadth(tickers)
    assert snap.universe_count == 1

"""Unit tests for BTC market regime."""

from decimal import Decimal

from shared.indicators import Candle
from shared.market_regime import analyze_btc_market_regime


class _FakeKline:
    def __init__(self, close: float, high: float | None = None, low: float | None = None):
        self.close = Decimal(str(close))
        self.high = Decimal(str(high if high is not None else close * 1.002))
        self.low = Decimal(str(low if low is not None else close * 0.998))


def _uptrend_klines(n: int = 120, start: float = 90000.0) -> list[_FakeKline]:
    out = []
    price = start
    for i in range(n):
        price += 50 + (i % 5) * 10
        out.append(_FakeKline(price))
    return out


def _downtrend_klines(n: int = 120, start: float = 95000.0) -> list[_FakeKline]:
    out = []
    price = start
    for i in range(n):
        price -= 50 + (i % 5) * 10
        out.append(_FakeKline(price))
    return out


def test_uptrend_suggests_long():
    up = _uptrend_klines()
    result = analyze_btc_market_regime(up, up)
    assert result is not None
    assert result.direction == "LONG"
    assert result.long_score > result.short_score


def test_downtrend_suggests_short():
    down = _downtrend_klines()
    result = analyze_btc_market_regime(down, down)
    assert result is not None
    assert result.direction == "SHORT"
    assert result.short_score > result.long_score

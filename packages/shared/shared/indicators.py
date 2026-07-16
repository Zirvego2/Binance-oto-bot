"""Teknik gosterge hesaplamalari (sartname bolum 15).

Gostergeler (EMA/RSI/ATR) piyasa analizi icin kullanilir; bu hesaplamalar
istatistiksel dogasi nedeniyle ``float`` ile yapilir (Binance'in kendisi de
kline degerlerini float/string olarak saglar ve gosterge hesaplari finansal
"para" islemleri degildir). Emir miktari, fiyat ve teminat gibi PARASAL
degerler ise her zaman ``Decimal`` ile hesaplanir (bkz. ``decimal_utils``,
``roi.py``, ``position_sizing.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


def ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average. Ilk deger basit ortalama (SMA) ile baslar."""

    if period <= 0:
        raise ValueError("period pozitif olmalidir")
    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)
    result: list[float] = []
    sma = sum(values[:period]) / period
    result.append(sma)
    prev = sma
    for value in values[period:]:
        current = (value - prev) * multiplier + prev
        result.append(current)
        prev = current
    return result


def rsi(values: list[float], period: int = 14) -> list[float]:
    """Wilder's RSI (Relative Strength Index)."""

    if period <= 0:
        raise ValueError("period pozitif olmalidir")
    if len(values) < period + 1:
        return []

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result: list[float] = []

    def _rsi_from_avgs(g: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = g / loss
        return 100 - (100 / (1 + rs))

    result.append(_rsi_from_avgs(avg_gain, avg_loss))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result.append(_rsi_from_avgs(avg_gain, avg_loss))

    return result


@dataclass(frozen=True, slots=True)
class Candle:
    high: float
    low: float
    close: float


def true_range(prev_close: float, high: float, low: float) -> float:
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close),
    )


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    """Wilder's Average True Range."""

    if period <= 0:
        raise ValueError("period pozitif olmalidir")
    if len(candles) < period + 1:
        return []

    trs: list[float] = []
    for i in range(1, len(candles)):
        trs.append(true_range(candles[i - 1].close, candles[i].high, candles[i].low))

    result: list[float] = []
    avg = sum(trs[:period]) / period
    result.append(avg)
    for tr in trs[period:]:
        avg = (avg * (period - 1) + tr) / period
        result.append(avg)
    return result


def sma(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period pozitif olmalidir")
    if len(values) < period:
        return []
    result: list[float] = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def crossed_above(fast_prev: float, fast_curr: float, slow_prev: float, slow_curr: float) -> bool:
    """Yukari kesisim: onceki mumda fast <= slow, guncel mumda fast > slow."""

    return fast_prev <= slow_prev and fast_curr > slow_curr


def crossed_below(fast_prev: float, fast_curr: float, slow_prev: float, slow_curr: float) -> bool:
    """Asagi kesisim: onceki mumda fast >= slow, guncel mumda fast < slow."""

    return fast_prev >= slow_prev and fast_curr < slow_curr


def adx(candles: list[Candle], period: int = 14) -> list[float]:
    """Wilder ADX (Average Directional Index)."""
    if period <= 0 or len(candles) < period * 2:
        return []

    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_list: list[float] = []
    for i in range(1, len(candles)):
        up_move = candles[i].high - candles[i - 1].high
        down_move = candles[i - 1].low - candles[i].low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr_list.append(true_range(candles[i - 1].close, candles[i].high, candles[i].low))

    def _wilder_smooth(values: list[float], p: int) -> list[float]:
        if len(values) < p:
            return []
        smoothed = [sum(values[:p])]
        for v in values[p:]:
            smoothed.append(smoothed[-1] - (smoothed[-1] / p) + v)
        return smoothed

    atr_sm = _wilder_smooth(tr_list, period)
    plus_sm = _wilder_smooth(plus_dm, period)
    minus_sm = _wilder_smooth(minus_dm, period)
    if not atr_sm or not plus_sm or not minus_sm:
        return []

    dx_values: list[float] = []
    length = min(len(atr_sm), len(plus_sm), len(minus_sm))
    for i in range(length):
        atr_val = atr_sm[i]
        if atr_val <= 0:
            dx_values.append(0.0)
            continue
        plus_di = 100 * plus_sm[i] / atr_val
        minus_di = 100 * minus_sm[i] / atr_val
        denom = plus_di + minus_di
        dx_values.append(0.0 if denom == 0 else 100 * abs(plus_di - minus_di) / denom)

    if len(dx_values) < period:
        return []
    adx_sm = _wilder_smooth(dx_values, period)
    return adx_sm


def bollinger_bands(
    values: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[list[float], list[float], list[float]]:
    """Bollinger Bands: middle (SMA), upper, lower."""
    if period <= 0 or len(values) < period:
        return [], [], []
    middle: list[float] = []
    upper: list[float] = []
    lower: list[float] = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        middle.append(mean)
        upper.append(mean + num_std * std)
        lower.append(mean - num_std * std)
    return middle, upper, lower


def vwap(closes: list[float], volumes: list[float]) -> list[float]:
    """Session VWAP (kumulatif hacim agirlikli ortalama fiyat)."""
    if not closes or len(closes) != len(volumes):
        return []
    result: list[float] = []
    cum_vol = 0.0
    cum_pv = 0.0
    for price, vol in zip(closes, volumes):
        if vol <= 0:
            result.append(result[-1] if result else price)
            continue
        cum_vol += vol
        cum_pv += price * vol
        result.append(cum_pv / cum_vol if cum_vol > 0 else price)
    return result

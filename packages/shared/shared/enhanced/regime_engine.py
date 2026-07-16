"""Piyasa rejimi tespit motoru."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared.indicators import Candle, adx, atr, bollinger_bands, ema, sma, vwap

from .types import MarketRegimeType, RegimeResult


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _ema_slope(values: list[float], lookback: int = 5) -> float:
    if len(values) < lookback + 1:
        return 0.0
    start = values[-lookback - 1]
    end = values[-1]
    if start == 0:
        return 0.0
    return (end - start) / start * 100


def detect_market_regime(
    *,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
    timeframe: str = "5m",
    btc_change_1h_pct: float = 0.0,
    btc_change_4h_pct: float = 0.0,
    rising_ratio: float = 0.5,
    avg_funding_pct: float = 0.0,
) -> RegimeResult:
    """Genel veya coin bazli rejim tespiti (deterministik)."""
    reasons: list[str] = []
    if len(closes) < 60:
        return RegimeResult(
            regime=MarketRegimeType.UNKNOWN,
            confidence=20.0,
            trend_strength=0.0,
            volatility_score=50.0,
            breadth_score=50.0,
            risk_off_score=50.0,
            reasons=["yetersiz_mum_verisi"],
            timeframe=timeframe,
            calculated_at=datetime.now(timezone.utc),
        )

    candles = [Candle(high=h, low=l, close=c) for h, l, c in zip(highs, lows, closes)]
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200) if len(closes) >= 200 else ema(closes, min(50, len(closes) - 1))
    atr_series = atr(candles, 14)
    adx_series = adx(candles, 14)
    _, bb_upper, bb_lower = bollinger_bands(closes, 20)
    vwap_series = vwap(closes, volumes)

    price = closes[-1]
    atr_pct = (atr_series[-1] / price * 100) if atr_series and price else 0.0
    adx_val = adx_series[-1] if adx_series else 0.0
    bb_width = 0.0
    if bb_upper and bb_lower and bb_upper[-1] > 0:
        mid = (bb_upper[-1] + bb_lower[-1]) / 2
        bb_width = ((bb_upper[-1] - bb_lower[-1]) / mid * 100) if mid else 0.0

    ema9_slope = _ema_slope(ema9) if ema9 else 0.0
    ema21_slope = _ema_slope(ema21) if ema21 else 0.0
    trend_strength = _clamp(adx_val * 1.5 + abs(ema9_slope) * 5)
    volatility_score = _clamp(atr_pct * 8 + bb_width * 2)
    breadth_score = _clamp(rising_ratio * 100)
    risk_off_score = _clamp(
        max(0, -btc_change_1h_pct * 5)
        + max(0, -btc_change_4h_pct * 3)
        + max(0, abs(avg_funding_pct) * 10)
        + max(0, 50 - rising_ratio * 100)
    )

    bullish = (
        ema9 and ema21 and ema50
        and ema9[-1] > ema21[-1] > ema50[-1]
        and price > ema50[-1]
        and ema9_slope > 0
    )
    bearish = (
        ema9 and ema21 and ema50
        and ema9[-1] < ema21[-1] < ema50[-1]
        and price < ema50[-1]
        and ema9_slope < 0
    )

    vwap_above = vwap_series and price >= vwap_series[-1]

    regime = MarketRegimeType.UNKNOWN
    confidence = 50.0

    if risk_off_score >= 70:
        regime = MarketRegimeType.RISK_OFF
        confidence = risk_off_score
        reasons.append("risk_off_puani_yuksek")
    elif volatility_score >= 75:
        regime = MarketRegimeType.HIGH_VOLATILITY
        confidence = volatility_score
        reasons.append(f"atr_yuksek_{atr_pct:.2f}%")
    elif volatility_score <= 25:
        regime = MarketRegimeType.LOW_VOLATILITY
        confidence = 100 - volatility_score
        reasons.append("dusuk_volatilite")
    elif bullish and trend_strength >= 55:
        regime = MarketRegimeType.STRONG_UPTREND if trend_strength >= 70 else MarketRegimeType.WEAK_UPTREND
        confidence = trend_strength
        reasons.append("yukari_trend")
    elif bearish and trend_strength >= 55:
        regime = MarketRegimeType.STRONG_DOWNTREND if trend_strength >= 70 else MarketRegimeType.WEAK_DOWNTREND
        confidence = trend_strength
        reasons.append("asagi_trend")
    elif bb_width > 0 and price > bb_upper[-1] and volumes[-1] > (sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]):
        regime = MarketRegimeType.BREAKOUT
        confidence = 65.0
        reasons.append("bollinger_ust_kirilim")
    elif bb_width > 0 and price < bb_lower[-1]:
        regime = MarketRegimeType.BREAKDOWN
        confidence = 65.0
        reasons.append("bollinger_alt_kirilim")
    else:
        regime = MarketRegimeType.SIDEWAYS
        confidence = 60.0
        reasons.append("net_trend_yok")

    if vwap_above and regime in (MarketRegimeType.STRONG_UPTREND, MarketRegimeType.WEAK_UPTREND):
        reasons.append("fiyat_vwap_ustu")
    elif not vwap_above and regime in (MarketRegimeType.STRONG_DOWNTREND, MarketRegimeType.WEAK_DOWNTREND):
        reasons.append("fiyat_vwap_alti")

    raw: dict[str, Any] = {
        "price": price,
        "atr_pct": atr_pct,
        "adx": adx_val,
        "bb_width_pct": bb_width,
        "ema9_slope": ema9_slope,
        "ema21_slope": ema21_slope,
        "btc_change_1h_pct": btc_change_1h_pct,
        "btc_change_4h_pct": btc_change_4h_pct,
        "rising_ratio": rising_ratio,
    }

    return RegimeResult(
        regime=regime,
        confidence=_clamp(confidence),
        trend_strength=_clamp(trend_strength),
        volatility_score=_clamp(volatility_score),
        breadth_score=_clamp(breadth_score),
        risk_off_score=_clamp(risk_off_score),
        reasons=reasons,
        timeframe=timeframe,
        raw_metrics=raw,
        calculated_at=datetime.now(timezone.utc),
    )

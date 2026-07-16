"""BTC coklu zaman dilimi analizi."""

from __future__ import annotations

from shared.indicators import ema

from .regime_engine import detect_market_regime


def analyze_btc_multi_timeframe(
    klines_by_tf: dict[str, tuple[list[float], list[float], list[float], list[float]]],
) -> dict:
    """klines_by_tf: timeframe -> (closes, highs, lows, volumes)"""
    directions: list[str] = []
    strengths: list[float] = []
    volatilities: list[float] = []

    for tf, (closes, highs, lows, volumes) in klines_by_tf.items():
        if len(closes) < 30:
            continue
        regime = detect_market_regime(
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            timeframe=tf,
        )
        if regime.regime.value.endswith("UPTREND"):
            directions.append("LONG")
        elif regime.regime.value.endswith("DOWNTREND"):
            directions.append("SHORT")
        else:
            directions.append("NEUTRAL")
        strengths.append(regime.trend_strength)
        volatilities.append(regime.volatility_score)

    long_count = directions.count("LONG")
    short_count = directions.count("SHORT")
    if long_count > short_count and long_count >= 2:
        btc_direction = "LONG"
    elif short_count > long_count and short_count >= 2:
        btc_direction = "SHORT"
    else:
        btc_direction = "NEUTRAL"

    alignment = max(long_count, short_count) / max(len(directions), 1) * 100
    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    avg_vol = sum(volatilities) / len(volatilities) if volatilities else 50.0
    btc_risk = min(100.0, avg_vol * 0.6 + (100 - alignment) * 0.4)

    change_1h = 0.0
    change_4h = 0.0
    if "5m" in klines_by_tf:
        closes = klines_by_tf["5m"][0]
        if len(closes) >= 12:
            change_1h = (closes[-1] - closes[-12]) / closes[-12] * 100 if closes[-12] else 0
        if len(closes) >= 48:
            change_4h = (closes[-1] - closes[-48]) / closes[-48] * 100 if closes[-48] else 0

    return {
        "btc_direction": btc_direction,
        "btc_trend_strength": avg_strength,
        "btc_volatility": avg_vol,
        "btc_risk_score": btc_risk,
        "multi_timeframe_alignment": alignment,
        "btc_change_1h_pct": change_1h,
        "btc_change_4h_pct": change_4h,
        "timeframe_directions": dict(zip(klines_by_tf.keys(), directions)),
    }

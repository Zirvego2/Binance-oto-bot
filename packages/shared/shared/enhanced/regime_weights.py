"""Rejime gore dinamik strateji agirliklari."""

from __future__ import annotations

from typing import Any

from .types import MarketRegimeType

DEFAULT_TREND_WEIGHTS: dict[str, float] = {
    "trend": 0.25,
    "ema": 0.20,
    "adx": 0.15,
    "volume": 0.15,
    "rsi": 0.10,
    "open_interest": 0.05,
    "spread": 0.05,
    "funding": 0.05,
}

DEFAULT_SIDEWAYS_WEIGHTS: dict[str, float] = {
    "rsi": 0.25,
    "bollinger": 0.20,
    "vwap": 0.15,
    "volume": 0.10,
    "spread": 0.10,
    "volatility": 0.10,
    "funding": 0.05,
    "trend": 0.05,
}

DEFAULT_HIGH_VOL_WEIGHTS: dict[str, float] = {
    "spread": 0.20,
    "atr": 0.20,
    "volume": 0.15,
    "trend": 0.15,
    "liquidation_distance": 0.15,
    "funding": 0.10,
    "open_interest": 0.05,
}

TREND_REGIMES = {
    MarketRegimeType.STRONG_UPTREND,
    MarketRegimeType.WEAK_UPTREND,
    MarketRegimeType.STRONG_DOWNTREND,
    MarketRegimeType.WEAK_DOWNTREND,
    MarketRegimeType.BREAKOUT,
    MarketRegimeType.BREAKDOWN,
}


def resolve_indicator_weights(
    regime: MarketRegimeType,
    profile_overrides: dict[str, Any] | None = None,
) -> dict[str, float]:
    if profile_overrides and profile_overrides.get("indicator_weights"):
        weights = dict(profile_overrides["indicator_weights"])
    elif regime in TREND_REGIMES:
        weights = dict(DEFAULT_TREND_WEIGHTS)
    elif regime == MarketRegimeType.HIGH_VOLATILITY:
        weights = dict(DEFAULT_HIGH_VOL_WEIGHTS)
    elif regime in (MarketRegimeType.SIDEWAYS, MarketRegimeType.LOW_VOLATILITY):
        weights = dict(DEFAULT_SIDEWAYS_WEIGHTS)
    else:
        weights = dict(DEFAULT_TREND_WEIGHTS)

    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def regime_min_signal_score(
    base_min: float,
    regime: MarketRegimeType,
    *,
    high_volatility_score: float,
    high_volatility_threshold: float,
    high_volatility_min_signal_score: float,
    unknown_regime_min_signal_score: float,
) -> float:
    if regime == MarketRegimeType.UNKNOWN:
        return max(base_min, unknown_regime_min_signal_score)
    if regime == MarketRegimeType.HIGH_VOLATILITY or high_volatility_score >= high_volatility_threshold:
        return max(base_min, high_volatility_min_signal_score)
    return base_min


def regime_alignment_score(direction: str, regime: MarketRegimeType) -> float:
    if direction == "LONG":
        if regime in (MarketRegimeType.STRONG_UPTREND, MarketRegimeType.WEAK_UPTREND, MarketRegimeType.BREAKOUT):
            return 90.0
        if regime in (MarketRegimeType.STRONG_DOWNTREND, MarketRegimeType.BREAKDOWN, MarketRegimeType.RISK_OFF):
            return 20.0
        if regime == MarketRegimeType.SIDEWAYS:
            return 50.0
    if direction == "SHORT":
        if regime in (MarketRegimeType.STRONG_DOWNTREND, MarketRegimeType.WEAK_DOWNTREND, MarketRegimeType.BREAKDOWN):
            return 90.0
        if regime in (MarketRegimeType.STRONG_UPTREND, MarketRegimeType.BREAKOUT, MarketRegimeType.RISK_OFF):
            return 20.0
        if regime == MarketRegimeType.SIDEWAYS:
            return 50.0
    return 50.0

"""LONG/SHORT sinyal puanlama motoru (sartname bolum 15-18).

0-100 arasinda aciklanabilir bir puan uretir; her alt bilesen (trend, EMA,
RSI, hacim, volatilite, spread, funding, open interest) ayri ayri
kaydedilir ve admin paneline "neden bu karar verildi" seklinde sunulur.
Yapay zeka / kara kutu model KULLANILMAZ.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import SignalDecision
from .indicators import crossed_above, crossed_below


@dataclass(frozen=True, slots=True)
class StrategyThresholds:
    rsi_long_min: float = 50.0
    rsi_long_max: float = 65.0
    rsi_short_min: float = 35.0
    rsi_short_max: float = 50.0
    volume_multiplier_min: float = 1.2
    max_spread_pct: float = 0.15
    max_funding_rate_pct: float = 0.75
    max_volatility_atr_pct: float = 8.0
    min_signal_score: float = 60.0
    long_enabled: bool = True
    short_enabled: bool = True


@dataclass(frozen=True, slots=True)
class SignalInputs:
    symbol: str
    price: float
    mark_price: float
    ema_fast: float
    ema_fast_prev: float
    ema_mid: float
    ema_mid_prev: float
    ema_slow: float
    rsi_value: float
    atr_value: float
    current_volume: float
    avg_volume_20: float
    volume_24h_usdt: float
    spread_pct: float
    funding_rate_pct: float
    open_interest: float | None
    thresholds: StrategyThresholds
    # Uygunluk / risk on-kontrolleri (worker tarafindan doldurulur)
    is_blacklisted: bool = False
    has_open_position: bool = False
    cooldown_active: bool = False
    daily_loss_limit_reached: bool = False
    max_positions_reached: bool = False
    has_enough_candles: bool = True
    min_notional_satisfiable: bool = True
    long_position_disabled: bool = False
    short_position_disabled: bool = False


@dataclass(frozen=True, slots=True)
class SignalScoreBreakdown:
    trend_score: float
    ema_score: float
    rsi_score: float
    volume_score: float
    volatility_score: float
    spread_score: float
    funding_score: float
    open_interest_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class SignalResult:
    symbol: str
    breakdown: SignalScoreBreakdown
    suggested_side: str | None  # "LONG" | "SHORT" | None
    decision: SignalDecision
    reason: str


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _score_rsi(rsi_value: float, lo: float, hi: float) -> float:
    """RSI hedef araligin ortasina ne kadar yakinsa o kadar yuksek puan."""

    if lo <= rsi_value <= hi:
        mid = (lo + hi) / 2
        span = max(hi - lo, 1e-6) / 2
        distance = abs(rsi_value - mid) / span
        return _clamp(100 - distance * 40)
    # Aralik disindaysa mesafeye gore hizla dusen puan
    distance = min(abs(rsi_value - lo), abs(rsi_value - hi))
    return _clamp(50 - distance * 5)


def evaluate_signal(inputs: SignalInputs) -> SignalResult:
    t = inputs.thresholds

    ema_bull = inputs.ema_fast > inputs.ema_mid and inputs.price > inputs.ema_slow
    ema_bear = inputs.ema_fast < inputs.ema_mid and inputs.price < inputs.ema_slow
    bullish_cross = crossed_above(inputs.ema_fast_prev, inputs.ema_fast, inputs.ema_mid_prev, inputs.ema_mid)
    bearish_cross = crossed_below(inputs.ema_fast_prev, inputs.ema_fast, inputs.ema_mid_prev, inputs.ema_mid)

    trend_score = 0.0
    if ema_bull:
        trend_score = 70.0 + (20.0 if bullish_cross else 0.0)
    elif ema_bear:
        trend_score = 70.0 + (20.0 if bearish_cross else 0.0)
    trend_score = _clamp(trend_score)

    ema_spread_pct = abs(inputs.ema_fast - inputs.ema_mid) / inputs.ema_mid * 100 if inputs.ema_mid else 0.0
    ema_score = _clamp(50 + ema_spread_pct * 10)

    volume_ratio = inputs.current_volume / inputs.avg_volume_20 if inputs.avg_volume_20 > 0 else 0.0
    volume_score = _clamp((volume_ratio / max(t.volume_multiplier_min, 0.01)) * 60)

    volatility_pct = inputs.atr_value / inputs.price * 100 if inputs.price > 0 else 0.0
    if volatility_pct <= t.max_volatility_atr_pct:
        volatility_score = _clamp(100 - (volatility_pct / max(t.max_volatility_atr_pct, 0.01)) * 30)
    else:
        volatility_score = _clamp(40 - (volatility_pct - t.max_volatility_atr_pct) * 5)

    if inputs.spread_pct <= t.max_spread_pct:
        spread_score = _clamp(100 - (inputs.spread_pct / max(t.max_spread_pct, 0.0001)) * 40)
    else:
        spread_score = _clamp(20 - (inputs.spread_pct - t.max_spread_pct) * 10)

    abs_funding = abs(inputs.funding_rate_pct)
    if abs_funding <= t.max_funding_rate_pct:
        funding_score = _clamp(100 - (abs_funding / max(t.max_funding_rate_pct, 0.0001)) * 30)
    else:
        funding_score = _clamp(20 - (abs_funding - t.max_funding_rate_pct) * 10)

    open_interest_score = 60.0 if inputs.open_interest and inputs.open_interest > 0 else 40.0

    rsi_long_score = _score_rsi(inputs.rsi_value, t.rsi_long_min, t.rsi_long_max)
    rsi_short_score = _score_rsi(inputs.rsi_value, t.rsi_short_min, t.rsi_short_max)

    weights = {
        "trend": 0.25,
        "ema": 0.10,
        "rsi": 0.20,
        "volume": 0.15,
        "volatility": 0.10,
        "spread": 0.10,
        "funding": 0.07,
        "oi": 0.03,
    }

    def _total(rsi_score: float) -> float:
        return (
            trend_score * weights["trend"]
            + ema_score * weights["ema"]
            + rsi_score * weights["rsi"]
            + volume_score * weights["volume"]
            + volatility_score * weights["volatility"]
            + spread_score * weights["spread"]
            + funding_score * weights["funding"]
            + open_interest_score * weights["oi"]
        )

    long_total = _total(rsi_long_score)
    short_total = _total(rsi_short_score)

    # Portfoy limitleri (max pozisyon, cooldown, gunluk zarar vb.) sinyal uretiminde
    # engel degildir — yalnizca islem acma asamasinda kontrol edilir.
    hard_block_reason: str | None = None
    if inputs.is_blacklisted:
        hard_block_reason = "coin_blacklisted"
    elif not inputs.has_enough_candles:
        hard_block_reason = "insufficient_candle_history"
    elif inputs.spread_pct > t.max_spread_pct:
        hard_block_reason = "spread_too_wide"
    elif abs_funding > t.max_funding_rate_pct:
        hard_block_reason = "funding_rate_out_of_range"
    elif volatility_pct > t.max_volatility_atr_pct:
        hard_block_reason = "volatility_out_of_range"
    elif not inputs.min_notional_satisfiable:
        hard_block_reason = "min_notional_not_satisfiable"

    if hard_block_reason == "min_notional_not_satisfiable":
        decision = SignalDecision.SKIPPED_MIN_NOTIONAL
        chosen_score = max(long_total, short_total)
        breakdown = SignalScoreBreakdown(
            trend_score, ema_score, max(rsi_long_score, rsi_short_score), volume_score,
            volatility_score, spread_score, funding_score, open_interest_score, chosen_score,
        )
        return SignalResult(inputs.symbol, breakdown, None, decision, hard_block_reason)

    if hard_block_reason is not None:
        decision = SignalDecision.SKIPPED_RISK
        chosen_score = max(long_total, short_total)
        breakdown = SignalScoreBreakdown(
            trend_score, ema_score, max(rsi_long_score, rsi_short_score), volume_score,
            volatility_score, spread_score, funding_score, open_interest_score, chosen_score,
        )
        return SignalResult(inputs.symbol, breakdown, None, decision, hard_block_reason)

    long_conditions = (
        t.long_enabled
        and ema_bull
        and t.rsi_long_min <= inputs.rsi_value <= t.rsi_long_max
        and volume_ratio >= t.volume_multiplier_min
        and long_total >= t.min_signal_score
    )
    short_conditions = (
        t.short_enabled
        and ema_bear
        and t.rsi_short_min <= inputs.rsi_value <= t.rsi_short_max
        and volume_ratio >= t.volume_multiplier_min
        and short_total >= t.min_signal_score
    )

    if long_conditions and (not short_conditions or long_total >= short_total):
        breakdown = SignalScoreBreakdown(
            trend_score, ema_score, rsi_long_score, volume_score, volatility_score,
            spread_score, funding_score, open_interest_score, long_total,
        )
        return SignalResult(inputs.symbol, breakdown, "LONG", SignalDecision.LONG, "long_conditions_met")

    if short_conditions:
        breakdown = SignalScoreBreakdown(
            trend_score, ema_score, rsi_short_score, volume_score, volatility_score,
            spread_score, funding_score, open_interest_score, short_total,
        )
        return SignalResult(inputs.symbol, breakdown, "SHORT", SignalDecision.SHORT, "short_conditions_met")

    best_score = max(long_total, short_total)
    best_rsi_score = rsi_long_score if long_total >= short_total else rsi_short_score
    breakdown = SignalScoreBreakdown(
        trend_score, ema_score, best_rsi_score, volume_score, volatility_score,
        spread_score, funding_score, open_interest_score, best_score,
    )
    if not ema_bull and not ema_bear:
        return SignalResult(inputs.symbol, breakdown, None, SignalDecision.NOT_ELIGIBLE, "no_clear_trend")
    return SignalResult(inputs.symbol, breakdown, None, SignalDecision.WAIT, "conditions_not_yet_met")

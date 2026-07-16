"""Sinyal bazli risk puanlama motoru (0=yuksek guvenli, 100=cok riskli)."""

from __future__ import annotations

from decimal import Decimal

from .regime_weights import regime_alignment_score
from .types import MarketRegimeType, RiskLevel, RiskScoreResult


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def compute_risk_score(
    *,
    spread_pct: float,
    atr_pct: float,
    price_spike_pct: float,
    funding_rate_pct: float,
    oi_change_pct: float,
    liquidation_distance_pct: float,
    min_liquidation_distance_pct: float,
    symbol_fail_rate: float,
    symbol_drawdown_pct: float,
    regime: MarketRegimeType,
    direction: str,
    btc_direction: str,
    correlation_with_portfolio: float,
    daily_loss_ratio: float,
    consecutive_losses: int,
    max_consecutive_losses: int,
    data_stale: bool,
    api_healthy: bool,
    ws_healthy: bool,
    estimated_slippage_pct: float,
    max_allowed_risk_score: float,
    block_critical_risk: bool,
    high_risk_min_signal_score: float,
    signal_score: float,
) -> RiskScoreResult:
    reasons: list[str] = []
    blocking: list[str] = []
    score = 0.0

    score += _clamp(spread_pct * 80)
    if spread_pct > 0.1:
        reasons.append("spread_genis")

    score += _clamp(atr_pct * 6)
    if atr_pct > 5:
        reasons.append("yuksek_volatilite")

    score += _clamp(abs(price_spike_pct) * 8)
    score += _clamp(abs(funding_rate_pct) * 15)
    score += _clamp(abs(oi_change_pct) * 0.5)

    liq_gap = liquidation_distance_pct - float(min_liquidation_distance_pct)
    if liq_gap < 2:
        score += 25
        reasons.append("likidasyona_yakin_sl")
    elif liq_gap < 5:
        score += 10

    score += _clamp(symbol_fail_rate * 40)
    score += _clamp(symbol_drawdown_pct * 2)

    align = regime_alignment_score(direction, regime)
    score += _clamp(100 - align)

    if btc_direction == "SHORT" and direction == "LONG":
        score += 20
        reasons.append("btc_ters_yon")
    elif btc_direction == "LONG" and direction == "SHORT":
        score += 20
        reasons.append("btc_ters_yon")

    score += _clamp(correlation_with_portfolio * 30)
    if correlation_with_portfolio > 0.8:
        reasons.append("yuksek_korelasyon")

    score += _clamp(daily_loss_ratio * 50)
    if consecutive_losses >= max_consecutive_losses:
        score += 30
        blocking.append("max_consecutive_losses_reached")

    if data_stale:
        score += 15
        reasons.append("veri_guncel_degil")
    if not api_healthy or not ws_healthy:
        score += 20
        reasons.append("baglanti_sagligi_zayif")

    score += _clamp(estimated_slippage_pct * 40)
    score = _clamp(score)

    if score >= 85:
        level = RiskLevel.CRITICAL
    elif score >= 65:
        level = RiskLevel.HIGH
    elif score >= 40:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    if block_critical_risk and level == RiskLevel.CRITICAL:
        blocking.append("critical_risk_blocked")

    if level == RiskLevel.HIGH and signal_score < high_risk_min_signal_score:
        blocking.append("high_risk_min_signal_not_met")

    if score > max_allowed_risk_score:
        blocking.append("max_allowed_risk_score_exceeded")

    rec_leverage = max(1, int(7 * (1 - score / 120)))
    rec_margin_mult = Decimal(str(max(0.5, 1 - score / 200)))

    if blocking:
        action = "BLOCK"
    elif level == RiskLevel.HIGH:
        action = "CAUTION"
    else:
        action = "PROCEED"

    return RiskScoreResult(
        risk_score=score,
        risk_level=level,
        risk_reasons=reasons,
        blocking_reasons=blocking,
        recommended_max_leverage=rec_leverage,
        recommended_margin_multiplier=rec_margin_mult,
        recommended_action=action,
    )

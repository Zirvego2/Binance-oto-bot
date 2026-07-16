"""Gelismis karar motoru orkestrasyonu."""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any

from shared.signal_scoring import SignalResult

from .btc_mtf import analyze_btc_multi_timeframe
from .correlation import correlation_penalty, max_portfolio_correlation
from .regime_engine import detect_market_regime
from .regime_weights import regime_alignment_score, regime_min_signal_score
from .risk_reward import compute_risk_reward
from .risk_score import compute_risk_score
from .types import CandidateMetrics, EnhancedScanResult, MarketRegimeType, RegimeResult, RiskLevel

DEFAULT_OPPORTUNITY_WEIGHTS = {
    "signal": 0.35,
    "regime_alignment": 0.15,
    "expected_reward": 0.15,
    "liquidity": 0.10,
    "symbol_profile": 0.10,
    "risk_penalty": 0.10,
    "correlation_penalty": 0.05,
}


def _liquidity_score(spread_pct: float, volume_24h: float, min_volume: float) -> float:
    spread_part = max(0.0, 100 - spread_pct * 200)
    vol_part = min(100.0, (volume_24h / max(min_volume, 1)) * 20)
    return min(100.0, spread_part * 0.6 + vol_part * 0.4)


def _profile_score(profile: dict[str, Any] | None, shadow_mode: bool, weight: float) -> float:
    if not profile or int(profile.get("total_trades", 0)) < int(profile.get("min_sample", 10)):
        return 50.0
    win_rate = float(profile.get("win_rate", 50))
    confidence = float(profile.get("confidence_level", 50))
    score = win_rate
    if shadow_mode:
        score = 50 + (win_rate - 50) * weight
    return max(0.0, min(100.0, score))


def run_enhanced_scan(
    *,
    settings: Any,
    scan_signals: list[tuple[str, SignalResult, dict[str, Any]]],
    market_closes: list[float],
    market_highs: list[float],
    market_lows: list[float],
    market_volumes: list[float],
    btc_klines_by_tf: dict[str, tuple[list[float], list[float], list[float], list[float]]],
    rising_ratio: float,
    avg_funding_pct: float,
    open_position_closes: dict[str, list[float]],
    symbol_profiles: dict[str, dict[str, Any]],
    opportunity_weights: dict[str, float] | None = None,
    shadow_only: bool = True,
    strategy_version_id: str | None = None,
    api_healthy: bool = True,
    ws_healthy: bool = True,
) -> EnhancedScanResult:
    """scan_signals: (symbol, SignalResult, context dict with market fields)"""
    scan_id = str(uuid.uuid4())
    weights = opportunity_weights or DEFAULT_OPPORTUNITY_WEIGHTS

    btc_mtf = analyze_btc_multi_timeframe(btc_klines_by_tf)
    market_regime = detect_market_regime(
        closes=market_closes,
        highs=market_highs,
        lows=market_lows,
        volumes=market_volumes,
        timeframe=getattr(settings, "candle_timeframe", "5m"),
        btc_change_1h_pct=float(btc_mtf.get("btc_change_1h_pct", 0)),
        btc_change_4h_pct=float(btc_mtf.get("btc_change_4h_pct", 0)),
        rising_ratio=rising_ratio,
        avg_funding_pct=avg_funding_pct,
    )

    if getattr(settings, "block_trades_in_risk_off", True) and market_regime.regime == MarketRegimeType.RISK_OFF:
        return EnhancedScanResult(
            scan_id=scan_id,
            market_regime=market_regime,
            btc_mtf=btc_mtf,
            candidates=[],
            selected=None,
            shadow_only=shadow_only,
            strategy_version_id=strategy_version_id,
        )

    min_conf = float(getattr(settings, "min_regime_confidence", 40))
    if getattr(settings, "market_regime_enabled", True) and market_regime.confidence < min_conf:
        market_regime = RegimeResult(
            regime=MarketRegimeType.UNKNOWN,
            confidence=market_regime.confidence,
            trend_strength=market_regime.trend_strength,
            volatility_score=market_regime.volatility_score,
            breadth_score=market_regime.breadth_score,
            risk_off_score=market_regime.risk_off_score,
            reasons=market_regime.reasons + ["dusuk_rejim_guveni"],
            timeframe=market_regime.timeframe,
            raw_metrics=market_regime.raw_metrics,
            calculated_at=market_regime.calculated_at,
        )

    effective_min_score = regime_min_signal_score(
        float(settings.min_signal_score),
        market_regime.regime,
        high_volatility_score=market_regime.volatility_score,
        high_volatility_threshold=float(getattr(settings, "high_volatility_score_threshold", 75)),
        high_volatility_min_signal_score=float(getattr(settings, "high_volatility_min_signal_score", 65)),
        unknown_regime_min_signal_score=float(getattr(settings, "unknown_regime_min_signal_score", 60)),
    )

    candidates: list[CandidateMetrics] = []
    min_rr = Decimal(str(getattr(settings, "minimum_risk_reward_ratio", Decimal("1.2"))))

    for symbol, signal, ctx in scan_signals:
        if signal.suggested_side is None:
            continue
        direction = signal.suggested_side
        signal_score = float(signal.breakdown.total_score)
        if signal_score < effective_min_score:
            continue

        closes = ctx.get("closes") or []
        corr = 0.0
        if getattr(settings, "correlation_control_enabled", True) and closes:
            corr = max_portfolio_correlation(closes, open_position_closes)

        liq_dist = float(ctx.get("liquidation_distance_pct", 15))
        risk = compute_risk_score(
            spread_pct=float(ctx.get("spread_pct", 0)),
            atr_pct=float(ctx.get("atr_pct", 0)),
            price_spike_pct=float(ctx.get("price_spike_pct", 0)),
            funding_rate_pct=float(ctx.get("funding_rate_pct", 0)),
            oi_change_pct=float(ctx.get("oi_change_pct", 0)),
            liquidation_distance_pct=liq_dist,
            min_liquidation_distance_pct=float(settings.min_liquidation_distance_pct),
            symbol_fail_rate=float(ctx.get("symbol_fail_rate", 0)),
            symbol_drawdown_pct=float(ctx.get("symbol_drawdown_pct", 0)),
            regime=market_regime.regime,
            direction=direction,
            btc_direction=str(btc_mtf.get("btc_direction", "NEUTRAL")),
            correlation_with_portfolio=corr,
            daily_loss_ratio=float(ctx.get("daily_loss_ratio", 0)),
            consecutive_losses=int(ctx.get("consecutive_losses", 0)),
            max_consecutive_losses=int(settings.max_consecutive_losses),
            data_stale=bool(ctx.get("data_stale", False)),
            api_healthy=api_healthy,
            ws_healthy=ws_healthy,
            estimated_slippage_pct=float(settings.max_slippage_pct),
            max_allowed_risk_score=float(getattr(settings, "max_allowed_risk_score", 80)),
            block_critical_risk=bool(getattr(settings, "block_critical_risk", True)),
            high_risk_min_signal_score=float(getattr(settings, "high_risk_min_signal_score", 75)),
            signal_score=signal_score,
        )

        if risk.blocking_reasons and getattr(settings, "block_critical_risk", True):
            if risk.risk_level == RiskLevel.CRITICAL or "critical_risk_blocked" in risk.blocking_reasons:
                candidates.append(
                    CandidateMetrics(
                        symbol=symbol,
                        direction=direction,
                        signal_score=signal_score,
                        risk_score=risk.risk_score,
                        expected_reward_score=0,
                        expected_loss_score=0,
                        risk_reward_ratio=0,
                        regime_alignment_score=regime_alignment_score(direction, market_regime.regime),
                        symbol_profile_score=50,
                        liquidity_score=0,
                        correlation_penalty=0,
                        final_opportunity_score=0,
                        rank=0,
                        selected=False,
                        rejection_reason=",".join(risk.blocking_reasons),
                        risk_level=risk.risk_level,
                        blocking_reasons=risk.blocking_reasons,
                    )
                )
                continue

        entry = Decimal(str(ctx.get("mark_price", ctx.get("price", "0"))))
        qty = Decimal(str(ctx.get("quantity", "1")))
        rr_result = compute_risk_reward(
            entry_price=entry,
            quantity=qty,
            side=direction,
            leverage=int(settings.leverage),
            take_profit_roi_pct=settings.take_profit_roi_pct,
            stop_loss_roi_pct=settings.stop_loss_roi_pct,
            taker_commission_rate=settings.paper_taker_commission_rate,
            estimated_slippage_pct=settings.max_slippage_pct,
            win_rate=Decimal(str(ctx.get("win_rate", "0.5"))),
        )
        if rr_result.risk_reward_ratio < min_rr:
            candidates.append(
                CandidateMetrics(
                    symbol=symbol,
                    direction=direction,
                    signal_score=signal_score,
                    risk_score=risk.risk_score,
                    expected_reward_score=float(rr_result.net_expected_profit_usdt),
                    expected_loss_score=float(rr_result.net_expected_loss_usdt),
                    risk_reward_ratio=float(rr_result.risk_reward_ratio),
                    regime_alignment_score=regime_alignment_score(direction, market_regime.regime),
                    symbol_profile_score=50,
                    liquidity_score=0,
                    correlation_penalty=0,
                    final_opportunity_score=0,
                    rank=0,
                    selected=False,
                    rejection_reason="minimum_risk_reward_not_met",
                    risk_level=risk.risk_level,
                    blocking_reasons=["minimum_risk_reward_not_met"],
                )
            )
            continue

        corr_pen = correlation_penalty(
            corr,
            float(getattr(settings, "max_position_correlation", 0.8)),
            float(getattr(settings, "correlation_penalty_weight", 1.0)),
        )
        if getattr(settings, "block_high_correlation_trades", False) and corr_pen >= 50:
            rejection = "high_correlation_blocked"
        else:
            rejection = None

        profile = symbol_profiles.get(symbol)
        prof_score = _profile_score(
            profile,
            bool(getattr(settings, "symbol_profile_shadow_mode", True)),
            float(getattr(settings, "symbol_profile_weight", 0.3)),
        )
        liq_score = _liquidity_score(
            float(ctx.get("spread_pct", 0)),
            float(ctx.get("volume_24h", 0)),
            float(settings.min_24h_volume_usdt),
        )
        regime_align = regime_alignment_score(direction, market_regime.regime)
        reward_score = min(100.0, float(rr_result.risk_reward_ratio) * 40)

        final = (
            signal_score * weights["signal"]
            + regime_align * weights["regime_alignment"]
            + reward_score * weights["expected_reward"]
            + liq_score * weights["liquidity"]
            + prof_score * weights["symbol_profile"]
            - risk.risk_score * weights["risk_penalty"]
            - corr_pen * weights["correlation_penalty"]
        )

        candidates.append(
            CandidateMetrics(
                symbol=symbol,
                direction=direction,
                signal_score=signal_score,
                risk_score=risk.risk_score,
                expected_reward_score=reward_score,
                expected_loss_score=float(rr_result.net_expected_loss_usdt),
                risk_reward_ratio=float(rr_result.risk_reward_ratio),
                regime_alignment_score=regime_align,
                symbol_profile_score=prof_score,
                liquidity_score=liq_score,
                correlation_penalty=corr_pen,
                final_opportunity_score=final,
                rank=0,
                selected=False,
                rejection_reason=rejection,
                risk_level=risk.risk_level,
                blocking_reasons=risk.blocking_reasons,
            )
        )

    candidates.sort(key=lambda c: c.final_opportunity_score, reverse=True)
    ranked: list[CandidateMetrics] = []
    selected: CandidateMetrics | None = None
    for i, c in enumerate(candidates):
        is_sel = i == 0 and c.rejection_reason is None and not c.blocking_reasons
        item = replace(c, rank=i + 1, selected=is_sel)
        ranked.append(item)
        if is_sel:
            selected = item

    return EnhancedScanResult(
        scan_id=scan_id,
        market_regime=market_regime,
        btc_mtf=btc_mtf,
        candidates=ranked,
        selected=selected,
        shadow_only=shadow_only,
        strategy_version_id=strategy_version_id,
    )

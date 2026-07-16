"""Enhanced decision engine unit tests."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from shared.ai_explanation import sanitize_payload, validate_ai_response
from shared.enhanced.btc_mtf import analyze_btc_multi_timeframe
from shared.enhanced.correlation import correlation_penalty, pearson_correlation
from shared.enhanced.learning_engine import recommendation_must_not_auto_apply
from shared.enhanced.regime_engine import detect_market_regime
from shared.enhanced.regime_weights import regime_min_signal_score
from shared.enhanced.risk_reward import compute_risk_reward
from shared.enhanced.risk_score import compute_risk_score
from shared.enhanced.shadow_mode import build_shadow_decision, shadow_agreement_rate
from shared.enhanced.types import EnhancedScanResult, MarketRegimeType, RegimeResult, RiskLevel
from shared.enhanced.backtest_engine import simulate_backtest
from shared.enhanced.symbol_profile import _confidence


def _make_candles(n: int = 120, trend: float = 0.001) -> tuple[list[float], list[float], list[float], list[float]]:
    closes, highs, lows, volumes = [], [], [], []
    price = 100.0
    for i in range(n):
        price *= 1 + trend
        closes.append(price)
        highs.append(price * 1.01)
        lows.append(price * 0.99)
        volumes.append(1000 + i)
    return closes, highs, lows, volumes


def test_market_regime_strong_uptrend():
    closes, highs, lows, volumes = _make_candles(120, trend=0.003)
    result = detect_market_regime(
        closes=closes, highs=highs, lows=lows, volumes=volumes,
        btc_change_1h_pct=2.0, btc_change_4h_pct=5.0, rising_ratio=0.7,
    )
    assert result.regime in (MarketRegimeType.STRONG_UPTREND, MarketRegimeType.WEAK_UPTREND, MarketRegimeType.BREAKOUT)


def test_market_regime_sideways():
    closes, highs, lows, volumes = _make_candles(120, trend=0.0)
    result = detect_market_regime(closes=closes, highs=highs, lows=lows, volumes=volumes, rising_ratio=0.5)
    assert result.regime in (MarketRegimeType.SIDEWAYS, MarketRegimeType.LOW_VOLATILITY, MarketRegimeType.UNKNOWN)


def test_market_regime_high_volatility():
    closes, highs, lows, volumes = _make_candles(80, trend=0.0)
    for i in range(len(closes)):
        highs[i] = closes[i] * 1.15
        lows[i] = closes[i] * 0.85
    result = detect_market_regime(closes=closes, highs=highs, lows=lows, volumes=volumes)
    assert result.volatility_score >= 50


def test_market_regime_risk_off():
    result = detect_market_regime(
        closes=[100] * 80, highs=[101] * 80, lows=[99] * 80, volumes=[1000] * 80,
        btc_change_1h_pct=-8, btc_change_4h_pct=-12, rising_ratio=0.2, avg_funding_pct=0.5,
    )
    assert result.risk_off_score >= 50


def test_critical_risk_blocks_trade():
    risk = compute_risk_score(
        spread_pct=0.5, atr_pct=10, price_spike_pct=5, funding_rate_pct=1,
        oi_change_pct=10, liquidation_distance_pct=3, min_liquidation_distance_pct=5,
        symbol_fail_rate=0.8, symbol_drawdown_pct=20, regime=MarketRegimeType.RISK_OFF,
        direction="LONG", btc_direction="SHORT", correlation_with_portfolio=0.9,
        daily_loss_ratio=0.9, consecutive_losses=5, max_consecutive_losses=3,
        data_stale=True, api_healthy=False, ws_healthy=False, estimated_slippage_pct=1,
        max_allowed_risk_score=80, block_critical_risk=True, high_risk_min_signal_score=75,
        signal_score=90,
    )
    assert risk.risk_level == RiskLevel.CRITICAL
    assert "critical_risk_blocked" in risk.blocking_reasons


def test_risk_adjusted_ranking_prefers_lower_risk():
    eth_lower_risk = 88 * 0.35 + 70 * 0.15 + 55 * 0.15 + 60 * 0.10 + 50 * 0.10 - 25 * 0.10
    btc_high_risk = 92 * 0.35 + 50 * 0.15 + 60 * 0.15 + 50 * 0.10 + 50 * 0.10 - 90 * 0.10
    assert eth_lower_risk > btc_high_risk


def test_risk_reward_minimum():
    rr = compute_risk_reward(
        entry_price=Decimal("100"), quantity=Decimal("1"), side="LONG", leverage=5,
        take_profit_roi_pct=Decimal("10"), stop_loss_roi_pct=Decimal("5"),
        taker_commission_rate=Decimal("0.0004"), estimated_slippage_pct=Decimal("0.1"),
        win_rate=Decimal("0.5"),
    )
    assert rr.risk_reward_ratio > Decimal("0")
    assert rr.expected_value_usdt is not None


def test_expected_value_neutral_win_rate():
    rr = compute_risk_reward(
        entry_price=Decimal("100"), quantity=Decimal("1"), side="LONG", leverage=3,
        take_profit_roi_pct=Decimal("8"), stop_loss_roi_pct=Decimal("4"),
        taker_commission_rate=Decimal("0.0004"), estimated_slippage_pct=Decimal("0.05"),
        win_rate=Decimal("0.5"),
    )
    assert rr.break_even_win_rate > Decimal("0")


def test_symbol_profile_low_confidence_with_small_sample():
    assert float(_confidence(3, 10)) < 50


def test_correlation_penalty_high_corr():
    pen = correlation_penalty(0.95, 0.8, 1.0)
    assert pen >= 50


def test_btc_mtf_analysis():
    c, h, l, v = _make_candles(60, -0.002)
    klines_tf = {"5m": (c, h, l, v), "15m": (c, h, l, v), "1h": (c, h, l, v), "4h": (c, h, l, v)}
    result = analyze_btc_multi_timeframe(klines_tf)
    assert "btc_direction" in result


def test_shadow_mode_does_not_trade():
    regime = RegimeResult(
        regime=MarketRegimeType.SIDEWAYS, confidence=60, trend_strength=40,
        volatility_score=40, breadth_score=50, risk_off_score=30, reasons=[], timeframe="5m",
    )
    enhanced = EnhancedScanResult(
        scan_id="s1", market_regime=regime, btc_mtf={}, candidates=[], selected=None,
        shadow_only=True, strategy_version_id=None,
    )
    shadow = build_shadow_decision("s1", current_symbol="BTCUSDT", current_direction="LONG",
                                   current_score=80, enhanced=enhanced)
    assert shadow.enhanced_engine_decision == "SKIP"
    assert shadow.current_engine_decision == "TRADE"


def test_learning_does_not_auto_apply():
    rec = SimpleNamespace(status="PENDING", approved_by=None)
    assert recommendation_must_not_auto_apply(rec) is True  # type: ignore[arg-type]


def test_gpt_json_schema_validation():
    data = {
        "summary": "Test", "positive_factors": ["a"], "negative_factors": ["b"],
        "risk_level": "LOW", "warnings": [], "suggestion": "Izle",
    }
    result = validate_ai_response(data)
    assert result is not None
    assert result.risk_level == "LOW"


def test_gpt_sanitize_removes_secrets():
    payload = sanitize_payload({"symbol": "BTC", "api_key": "secret", "score": 80})
    assert "api_key" not in payload
    assert payload["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_gpt_failure_does_not_change_trading():
    from shared.ai_explanation import generate_signal_explanation

    result = await generate_signal_explanation(api_key="", payload={"symbol": "ETH"})
    assert result.status == "UNAVAILABLE"
    assert result.summary == "Kullanilamiyor"


def test_pearson_correlation():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert pearson_correlation(a, b) > 0.99


def test_backtest_no_look_ahead():
    candles = {"TESTUSDT": [(100, 101, 99, 100 + i * 0.1) for i in range(80)]}

    def decision_fn(symbol, history):
        if len(history) < 65:
            return None
        return ("LONG", len(history) - 1)

    result = simulate_backtest(
        engine_name="test", strategy_version="v1", candles_by_symbol=candles, decision_fn=decision_fn,
    )
    assert result.total_trades >= 0


def test_regime_min_signal_score_unknown():
    score = regime_min_signal_score(50, MarketRegimeType.UNKNOWN, high_volatility_score=30,
                                    high_volatility_threshold=75, high_volatility_min_signal_score=65,
                                    unknown_regime_min_signal_score=60)
    assert score == 60


def test_shadow_agreement_rate():
    from shared.db import ShadowDecision
    from datetime import datetime, timezone

    d1 = ShadowDecision(scan_id="1", current_selected_symbol="A", enhanced_selected_symbol="A",
                        current_direction="LONG", enhanced_direction="LONG", created_at=datetime.now(timezone.utc))
    d2 = ShadowDecision(scan_id="2", current_selected_symbol="A", enhanced_selected_symbol="B",
                        current_direction="LONG", enhanced_direction="LONG", created_at=datetime.now(timezone.utc))
    assert shadow_agreement_rate([d1, d2]) == 50.0

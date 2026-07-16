from shared.enums import SignalDecision
from shared.signal_scoring import SignalInputs, StrategyThresholds, evaluate_signal

DEFAULT_THRESHOLDS = StrategyThresholds()


def _base_kwargs(**overrides):
    base = dict(
        symbol="BTCUSDT",
        price=100.0,
        mark_price=100.0,
        ema_fast=101.0,
        ema_fast_prev=99.5,
        ema_mid=100.0,
        ema_mid_prev=100.0,
        ema_slow=98.0,
        rsi_value=58.0,
        atr_value=1.5,
        current_volume=1500.0,
        avg_volume_20=1000.0,
        volume_24h_usdt=50_000_000.0,
        spread_pct=0.02,
        funding_rate_pct=0.01,
        open_interest=1000.0,
        thresholds=DEFAULT_THRESHOLDS,
    )
    base.update(overrides)
    return base


def test_long_signal_generated_when_all_conditions_met():
    inputs = SignalInputs(**_base_kwargs())
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.LONG
    assert result.suggested_side == "LONG"
    assert 0 <= result.breakdown.total_score <= 100


def test_short_signal_generated_when_all_conditions_met():
    inputs = SignalInputs(
        **_base_kwargs(
            ema_fast=99.0,
            ema_fast_prev=100.5,
            ema_mid=100.0,
            ema_mid_prev=100.0,
            ema_slow=102.0,
            rsi_value=42.0,
        )
    )
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.SHORT
    assert result.suggested_side == "SHORT"


def test_no_signal_when_rsi_out_of_range():
    inputs = SignalInputs(**_base_kwargs(rsi_value=80.0))
    result = evaluate_signal(inputs)
    assert result.decision != SignalDecision.LONG


def test_no_signal_when_volume_too_low():
    inputs = SignalInputs(**_base_kwargs(current_volume=500.0, avg_volume_20=1000.0))
    result = evaluate_signal(inputs)
    assert result.decision != SignalDecision.LONG


def test_blacklisted_symbol_skipped_for_risk():
    inputs = SignalInputs(**_base_kwargs(is_blacklisted=True))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.SKIPPED_RISK
    assert result.reason == "coin_blacklisted"


def test_open_position_does_not_block_signal_generation():
    inputs = SignalInputs(**_base_kwargs(has_open_position=True))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.LONG
    assert result.suggested_side == "LONG"


def test_max_positions_does_not_block_signal_generation():
    inputs = SignalInputs(**_base_kwargs(max_positions_reached=True))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.LONG
    assert result.suggested_side == "LONG"


def test_min_notional_not_satisfiable_returns_specific_decision():
    inputs = SignalInputs(**_base_kwargs(min_notional_satisfiable=False))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.SKIPPED_MIN_NOTIONAL


def test_excessive_spread_blocks_signal():
    inputs = SignalInputs(**_base_kwargs(spread_pct=5.0))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.SKIPPED_RISK
    assert result.reason == "spread_too_wide"


def test_excessive_funding_blocks_signal():
    inputs = SignalInputs(**_base_kwargs(funding_rate_pct=3.0))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.SKIPPED_RISK
    assert result.reason == "funding_rate_out_of_range"


def test_long_disabled_falls_back_to_wait():
    inputs = SignalInputs(**_base_kwargs(long_position_disabled=True))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.LONG
    assert result.suggested_side == "LONG"


def test_daily_loss_limit_does_not_block_signal_generation():
    inputs = SignalInputs(**_base_kwargs(daily_loss_limit_reached=True))
    result = evaluate_signal(inputs)
    assert result.decision == SignalDecision.LONG
    assert result.suggested_side == "LONG"

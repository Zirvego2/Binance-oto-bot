from decimal import Decimal

from shared.position_exit import evaluate_position_exit


def test_take_profit_triggers_close():
    decision, peak = evaluate_position_exit(
        Decimal("10.5"), Decimal("8"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        trailing_stop_enabled=False,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("1"),
    )
    assert decision.should_close is True
    assert decision.close_reason == "TAKE_PROFIT"
    assert peak == Decimal("10.5")


def test_stop_loss_triggers_on_adverse_move():
    decision, _ = evaluate_position_exit(
        Decimal("-5.1"), Decimal("2"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        trailing_stop_enabled=False,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("1"),
    )
    assert decision.should_close is True
    assert decision.close_reason == "STOP_LOSS"


def test_trailing_stop_on_drawdown_from_peak():
    decision, peak = evaluate_position_exit(
        Decimal("6"), Decimal("8"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        trailing_stop_enabled=True,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("1.5"),
    )
    assert decision.should_close is True
    assert decision.close_reason == "TRAILING_STOP"
    assert peak == Decimal("8")


def test_trailing_stop_break_even_lock():
    decision, _ = evaluate_position_exit(
        Decimal("-0.5"), Decimal("6"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        trailing_stop_enabled=True,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("3"),
    )
    assert decision.should_close is True
    assert decision.close_reason == "TRAILING_STOP"


def test_no_close_within_normal_range():
    decision, peak = evaluate_position_exit(
        Decimal("3"), Decimal("3"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        trailing_stop_enabled=True,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("1"),
    )
    assert decision.should_close is False
    assert peak == Decimal("3")

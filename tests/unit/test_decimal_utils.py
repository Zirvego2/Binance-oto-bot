from decimal import Decimal

from shared.decimal_utils import quantize_price, quantize_step, round_up_to_step


def test_quantize_step_rounds_down_to_step_size():
    assert quantize_step(Decimal("1.23456"), Decimal("0.001")) == Decimal("1.234")


def test_quantize_step_exact_multiple_unchanged():
    assert quantize_step(Decimal("2.500"), Decimal("0.5")) == Decimal("2.5")


def test_quantize_step_rejects_non_positive_step():
    import pytest

    with pytest.raises(ValueError):
        quantize_step(Decimal("1"), Decimal("0"))


def test_quantize_price_rounds_to_tick_size():
    assert quantize_price(Decimal("27.9371"), Decimal("0.01")) == Decimal("27.94")


def test_round_up_to_step():
    assert round_up_to_step(Decimal("1.001"), Decimal("0.01")) == Decimal("1.01")

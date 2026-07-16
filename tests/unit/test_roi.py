from decimal import Decimal

from shared.enums import PositionSide
from shared.roi import (
    RoiPriceInputs,
    compute_realized_pnl,
    compute_roi_from_prices,
    compute_roi_prices,
    estimate_liquidation_price,
    liquidation_distance_pct,
)


def test_compute_realized_pnl_long_profit():
    pnl = compute_realized_pnl(Decimal("100"), Decimal("110"), Decimal("2"), PositionSide.LONG)
    assert pnl == Decimal("20")


def test_compute_realized_pnl_short_profit():
    pnl = compute_realized_pnl(Decimal("100"), Decimal("90"), Decimal("2"), PositionSide.SHORT)
    assert pnl == Decimal("20")


def test_long_take_profit_price_is_above_entry():
    inputs = RoiPriceInputs(
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        side=PositionSide.LONG,
        leverage=Decimal("5"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        taker_commission_rate=Decimal("0.0004"),
    )
    result = compute_roi_prices(inputs)
    assert result.take_profit_price > inputs.entry_price
    assert result.stop_loss_price < inputs.entry_price


def test_long_stop_loss_price_is_below_entry():
    inputs = RoiPriceInputs(
        entry_price=Decimal("2000"),
        quantity=Decimal("0.5"),
        side=PositionSide.LONG,
        leverage=Decimal("3"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
    )
    result = compute_roi_prices(inputs)
    assert result.stop_loss_price < inputs.entry_price
    assert result.take_profit_price > inputs.entry_price


def test_short_take_profit_price_is_below_entry():
    inputs = RoiPriceInputs(
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        side=PositionSide.SHORT,
        leverage=Decimal("5"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
    )
    result = compute_roi_prices(inputs)
    assert result.take_profit_price < inputs.entry_price


def test_short_stop_loss_price_is_above_entry():
    inputs = RoiPriceInputs(
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        side=PositionSide.SHORT,
        leverage=Decimal("5"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
    )
    result = compute_roi_prices(inputs)
    assert result.stop_loss_price > inputs.entry_price


def test_roi_price_move_approximates_roi_over_leverage():
    """ROI hedefi / kaldirac formulune yaklasik esitlik (komisyon paylari kucuk)."""

    inputs = RoiPriceInputs(
        entry_price=Decimal("100"),
        quantity=Decimal("1"),
        side=PositionSide.LONG,
        leverage=Decimal("5"),
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        taker_commission_rate=Decimal("0"),
    )
    result = compute_roi_prices(inputs)
    # %10 ROI / 5x kaldirac = %2 fiyat hareketi (komisyon sifir oldugunda tam esit)
    assert abs(result.take_profit_price_move_pct - Decimal("2")) < Decimal("0.01")


def test_compute_roi_from_prices_long():
    roi = compute_roi_from_prices(
        entry_price=Decimal("100"),
        current_price=Decimal("102"),
        quantity=Decimal("1"),
        leverage=Decimal("5"),
        side=PositionSide.LONG,
    )
    # fiyat %2 arttiginda, 5x kaldirac ile ROI ~%10
    assert abs(roi - Decimal("10")) < Decimal("0.01")


def test_compute_roi_from_prices_short():
    roi = compute_roi_from_prices(
        entry_price=Decimal("100"),
        current_price=Decimal("98"),
        quantity=Decimal("1"),
        leverage=Decimal("5"),
        side=PositionSide.SHORT,
    )
    assert abs(roi - Decimal("10")) < Decimal("0.01")


def test_liquidation_price_long_below_entry():
    liq = estimate_liquidation_price(Decimal("100"), Decimal("5"), PositionSide.LONG)
    assert liq < Decimal("100")


def test_liquidation_price_short_above_entry():
    liq = estimate_liquidation_price(Decimal("100"), Decimal("5"), PositionSide.SHORT)
    assert liq > Decimal("100")


def test_liquidation_distance_positive_when_safe():
    distance = liquidation_distance_pct(Decimal("95"), Decimal("80"), PositionSide.LONG)
    assert distance > Decimal("0")


def test_stop_loss_raises_when_zero_or_negative():
    import pytest

    with pytest.raises(ValueError):
        compute_roi_prices(
            RoiPriceInputs(
                entry_price=Decimal("0.001"),
                quantity=Decimal("1"),
                side=PositionSide.LONG,
                leverage=Decimal("5"),
                take_profit_roi_pct=Decimal("10"),
                stop_loss_roi_pct=Decimal("800"),
            )
        )

"""Unit tests for loss add trigger vs final stop."""

from decimal import Decimal

from shared.loss_add import effective_stop_loss_roi_pct, is_normal_market_position, should_loss_add


def test_effective_sl_uses_final_stop():
    roi = effective_stop_loss_roi_pct(
        Decimal("50"),
        loss_add_enabled=True,
        loss_add_max_count=1,
        loss_add_count=0,
    )
    assert roi == Decimal("50")


def test_should_loss_add_at_trigger():
    assert should_loss_add(
        Decimal("-25.1"),
        loss_add_trigger_roi_pct=Decimal("25"),
        stop_loss_roi_pct=Decimal("50"),
        loss_add_enabled=True,
        loss_add_max_count=1,
        loss_add_count=0,
        is_normal_position=True,
    )


def test_should_not_loss_add_at_final_stop():
    assert not should_loss_add(
        Decimal("-50"),
        loss_add_trigger_roi_pct=Decimal("25"),
        stop_loss_roi_pct=Decimal("50"),
        loss_add_enabled=True,
        loss_add_max_count=1,
        loss_add_count=0,
        is_normal_position=True,
    )


def test_should_not_loss_add_for_olta():
    assert not should_loss_add(
        Decimal("-25.1"),
        loss_add_trigger_roi_pct=Decimal("25"),
        stop_loss_roi_pct=Decimal("50"),
        loss_add_enabled=True,
        loss_add_max_count=1,
        loss_add_count=0,
        is_normal_position=is_normal_market_position(is_external=False, open_reason="limit_entry_filled"),
    )


def test_should_not_loss_add_after_max():
    assert not should_loss_add(
        Decimal("-30"),
        loss_add_trigger_roi_pct=Decimal("25"),
        stop_loss_roi_pct=Decimal("50"),
        loss_add_enabled=True,
        loss_add_max_count=1,
        loss_add_count=1,
        is_normal_position=True,
    )

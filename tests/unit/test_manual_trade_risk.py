"""Manuel islem risk kontrolleri."""

from __future__ import annotations

from decimal import Decimal

from shared.db import BotSettings
from shared.trading_risk import RiskContext, evaluate_manual_trade_risk, evaluate_portfolio_risk


def test_manual_trade_skips_auto_trading_check() -> None:
    settings = BotSettings(
        mode="live",
        bot_enabled=True,
        auto_trading_enabled=False,
        long_enabled=True,
        short_enabled=True,
        leverage=10,
        max_allowed_leverage=20,
        max_open_positions=8,
        max_open_positions_per_symbol=1,
        daily_max_loss_usdt=Decimal("100"),
        max_consecutive_losses=5,
    )
    ctx = RiskContext(
        open_positions_count=0,
        open_positions_for_symbol=0,
        pending_limit_entry_count=0,
        daily_loss_limit_reached=False,
        consecutive_losses=0,
        max_consecutive_losses_reached=False,
        is_blacklisted=False,
        cooldown_active=False,
        long_disabled_for_symbol=False,
        short_disabled_for_symbol=False,
        max_leverage_override=None,
    )

    auto = evaluate_portfolio_risk(settings, ctx, "LONG")
    manual = evaluate_manual_trade_risk(settings, ctx, "LONG")

    assert auto.ok is False
    assert auto.reason == "auto_trading_disabled"
    assert manual.ok is True

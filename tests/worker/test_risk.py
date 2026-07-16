"""worker/risk.py testleri: hesap/portfoy seviyesi risk kurallari."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, DailyStatistic, Position, SymbolRule
from shared.timezone_utils import local_today
from worker.risk import RiskContext, build_risk_context, check_liquidation_distance, evaluate_portfolio_risk


def _ctx(**overrides) -> RiskContext:
    base = dict(
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
    base.update(overrides)
    return RiskContext(**base)


@pytest.mark.asyncio
async def test_evaluate_portfolio_risk_ok(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(), "LONG")
    assert result.ok is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_bot_disabled_blocks_trade(settings_row: BotSettings):
    settings_row.bot_enabled = False
    result = evaluate_portfolio_risk(settings_row, _ctx(), "LONG")
    assert result.ok is False
    assert result.reason == "bot_disabled"


@pytest.mark.asyncio
async def test_auto_trading_disabled_blocks_trade(settings_row: BotSettings):
    settings_row.auto_trading_enabled = False
    result = evaluate_portfolio_risk(settings_row, _ctx(), "LONG")
    assert result.ok is False
    assert result.reason == "auto_trading_disabled"


@pytest.mark.asyncio
async def test_blacklisted_symbol_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(is_blacklisted=True), "LONG")
    assert result.ok is False
    assert result.reason == "symbol_blacklisted"


@pytest.mark.asyncio
async def test_cooldown_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(cooldown_active=True), "LONG")
    assert result.ok is False
    assert result.reason == "post_trade_cooldown_active"


@pytest.mark.asyncio
async def test_daily_loss_limit_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(daily_loss_limit_reached=True), "LONG")
    assert result.ok is False
    assert result.reason == "daily_max_loss_reached"


@pytest.mark.asyncio
async def test_max_consecutive_losses_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(max_consecutive_losses_reached=True), "LONG")
    assert result.ok is False
    assert result.reason == "max_consecutive_losses_reached"


@pytest.mark.asyncio
async def test_max_open_positions_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(
        settings_row, _ctx(open_positions_count=settings_row.max_open_positions), "LONG"
    )
    assert result.ok is False
    assert result.reason == "max_open_positions_reached"


@pytest.mark.asyncio
async def test_pending_limit_entries_do_not_block_max_open_positions(settings_row: BotSettings):
    """Bekleyen olta emirleri maks. acik pozisyon limitine dahil edilmez."""
    result = evaluate_portfolio_risk(
        settings_row,
        _ctx(
            open_positions_count=settings_row.max_open_positions - 1,
            pending_limit_entry_count=settings_row.max_open_positions,
        ),
        "LONG",
    )
    assert result.ok is True


@pytest.mark.asyncio
async def test_max_open_positions_per_symbol_blocks_trade(settings_row: BotSettings):
    result = evaluate_portfolio_risk(
        settings_row,
        _ctx(open_positions_for_symbol=settings_row.max_open_positions_per_symbol),
        "LONG",
    )
    assert result.ok is False
    assert result.reason == "max_open_positions_per_symbol_reached"


@pytest.mark.asyncio
async def test_long_disabled_globally_blocks_long(settings_row: BotSettings):
    settings_row.long_enabled = False
    result = evaluate_portfolio_risk(settings_row, _ctx(), "LONG")
    assert result.ok is False
    assert result.reason == "long_disabled"
    # SHORT hala serbest olmali
    assert evaluate_portfolio_risk(settings_row, _ctx(), "SHORT").ok is True


@pytest.mark.asyncio
async def test_short_disabled_for_symbol_blocks_short(settings_row: BotSettings):
    result = evaluate_portfolio_risk(settings_row, _ctx(short_disabled_for_symbol=True), "SHORT")
    assert result.ok is False
    assert result.reason == "short_disabled"


@pytest.mark.asyncio
async def test_leverage_exceeds_max_allowed_blocks_trade(settings_row: BotSettings):
    settings_row.leverage = settings_row.max_allowed_leverage + 5
    result = evaluate_portfolio_risk(settings_row, _ctx(), "LONG")
    assert result.ok is False
    assert result.reason == "leverage_exceeds_max_allowed"


@pytest.mark.asyncio
async def test_symbol_rule_leverage_override_raises_limit(settings_row: BotSettings):
    settings_row.leverage = settings_row.max_allowed_leverage + 5
    result = evaluate_portfolio_risk(
        settings_row, _ctx(max_leverage_override=settings_row.leverage), "LONG"
    )
    assert result.ok is True


def test_check_liquidation_distance_rejects_too_close():
    result = check_liquidation_distance(Decimal("5"), Decimal("10"))
    assert result.ok is False
    assert result.reason == "liquidation_distance_too_small"


def test_check_liquidation_distance_accepts_safe_distance():
    result = check_liquidation_distance(Decimal("15"), Decimal("10"))
    assert result.ok is True


@pytest.mark.asyncio
async def test_build_risk_context_reads_open_positions_and_blacklist(
    session: AsyncSession, settings_row: BotSettings, symbol_row
):
    session.add(
        Position(
            symbol=symbol_row.symbol, side="LONG", status="OPEN", bot_mode="paper", margin_type="ISOLATED",
            leverage=5, margin_usdt=Decimal("10"), quantity=Decimal("0.001"), notional_usdt=Decimal("50"),
            entry_price=Decimal("50000"), mark_price=Decimal("50000"), liquidation_price=Decimal("40000"),
            stop_loss_price=Decimal("48000"), take_profit_price=Decimal("55000"),
            open_commission_usdt=Decimal("0.02"), open_order_id="x1", opened_at=datetime.now(timezone.utc),
        )
    )
    session.add(SymbolRule(symbol=symbol_row.symbol, is_blacklisted=True))
    await session.commit()

    ctx = await build_risk_context(session, settings_row, symbol_row.symbol)
    assert ctx.open_positions_count == 1
    assert ctx.open_positions_for_symbol == 1
    assert ctx.is_blacklisted is True


@pytest.mark.asyncio
async def test_build_risk_context_detects_cooldown(session: AsyncSession, settings_row: BotSettings, symbol_row):
    session.add(
        SymbolRule(
            symbol=symbol_row.symbol,
            cooldown_until=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )
    await session.commit()

    ctx = await build_risk_context(session, settings_row, symbol_row.symbol)
    assert ctx.cooldown_active is True


@pytest.mark.asyncio
async def test_build_risk_context_detects_daily_loss_limit(
    session: AsyncSession, settings_row: BotSettings, symbol_row
):
    today = local_today()
    session.add(
        DailyStatistic(
            stat_date=today, bot_mode="paper", trades_count=2, winning_trades=0, losing_trades=2,
            win_rate_pct=Decimal("0"), gross_pnl_usdt=-settings_row.daily_max_loss_usdt,
            net_pnl_usdt=-settings_row.daily_max_loss_usdt, total_commission_usdt=Decimal("0"),
            total_funding_usdt=Decimal("0"), consecutive_losses=2,
        )
    )
    await session.commit()

    ctx = await build_risk_context(session, settings_row, symbol_row.symbol)
    assert ctx.daily_loss_limit_reached is True
    assert ctx.consecutive_losses == 2

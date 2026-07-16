"""Portfoy seviyesi risk kontrolleri (musteri bazli)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, Order, Position
from shared.tenant_scope import get_or_create_daily_statistic, get_or_create_symbol_rule
from shared.timezone_utils import local_today

_PENDING_LIMIT_STATUSES = ("PENDING", "NEW", "SUBMITTING")


async def count_filled_open_positions(
    session: AsyncSession,
    bot_mode: str,
    admin_id: str,
    *,
    symbol: str | None = None,
) -> int:
    query = select(func.count()).select_from(Position).where(
        Position.status == "OPEN",
        Position.bot_mode == bot_mode,
        Position.admin_id == admin_id,
    )
    if symbol is not None:
        query = query.where(Position.symbol == symbol)
    result = await session.execute(query)
    return int(result.scalar_one())


async def count_pending_limit_entry_orders(
    session: AsyncSession,
    bot_mode: str,
    admin_id: str,
    *,
    symbol: str | None = None,
) -> int:
    query = (
        select(func.count())
        .select_from(Order)
        .where(
            Order.order_type == "LIMIT",
            Order.purpose == "OPEN",
            Order.status.in_(_PENDING_LIMIT_STATUSES),
            Order.bot_mode == bot_mode,
            Order.admin_id == admin_id,
        )
    )
    if symbol is not None:
        query = query.where(Order.symbol == symbol)
    result = await session.execute(query)
    return int(result.scalar_one())


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    ok: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RiskContext:
    open_positions_count: int
    open_positions_for_symbol: int
    pending_limit_entry_count: int
    daily_loss_limit_reached: bool
    consecutive_losses: int
    max_consecutive_losses_reached: bool
    is_blacklisted: bool
    cooldown_active: bool
    long_disabled_for_symbol: bool
    short_disabled_for_symbol: bool
    max_leverage_override: int | None


async def build_risk_context(session: AsyncSession, settings_row: BotSettings, symbol: str) -> RiskContext:
    admin_id = settings_row.admin_id or ""
    open_positions_count = await count_filled_open_positions(session, settings_row.mode, admin_id)
    open_for_symbol = await count_filled_open_positions(session, settings_row.mode, admin_id, symbol=symbol)
    pending_limit_entry_count = await count_pending_limit_entry_orders(session, settings_row.mode, admin_id)

    today = local_today()
    stat = await get_or_create_daily_statistic(session, admin_id, settings_row.mode, today)
    daily_loss = abs(stat.net_pnl_usdt) if stat.net_pnl_usdt < 0 else Decimal("0")
    daily_loss_limit_reached = daily_loss >= settings_row.daily_max_loss_usdt
    consecutive_losses = stat.consecutive_losses
    max_consecutive_reached = consecutive_losses >= settings_row.max_consecutive_losses

    rule = await get_or_create_symbol_rule(session, admin_id, symbol)

    cooldown_active = False
    if rule.cooldown_until:
        cooldown_until = rule.cooldown_until
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        cooldown_active = cooldown_until > datetime.now(timezone.utc)

    return RiskContext(
        open_positions_count=open_positions_count,
        open_positions_for_symbol=open_for_symbol,
        pending_limit_entry_count=pending_limit_entry_count,
        daily_loss_limit_reached=daily_loss_limit_reached,
        consecutive_losses=consecutive_losses,
        max_consecutive_losses_reached=max_consecutive_reached,
        is_blacklisted=rule.is_blacklisted,
        cooldown_active=cooldown_active,
        long_disabled_for_symbol=not rule.long_enabled,
        short_disabled_for_symbol=not rule.short_enabled,
        max_leverage_override=rule.max_leverage_override,
    )


def _portfolio_checks(settings_row: BotSettings, ctx: RiskContext, side: str) -> RiskCheckResult:
    if not settings_row.bot_enabled:
        return RiskCheckResult(False, "bot_disabled")
    if ctx.is_blacklisted:
        return RiskCheckResult(False, "symbol_blacklisted")
    if ctx.cooldown_active:
        return RiskCheckResult(False, "post_trade_cooldown_active")
    if ctx.daily_loss_limit_reached:
        return RiskCheckResult(False, "daily_max_loss_reached")
    if ctx.max_consecutive_losses_reached:
        return RiskCheckResult(False, "max_consecutive_losses_reached")
    if ctx.open_positions_count >= settings_row.max_open_positions:
        return RiskCheckResult(False, "max_open_positions_reached")
    if ctx.open_positions_for_symbol >= settings_row.max_open_positions_per_symbol:
        return RiskCheckResult(False, "max_open_positions_per_symbol_reached")
    if side == "LONG" and (not settings_row.long_enabled or ctx.long_disabled_for_symbol):
        return RiskCheckResult(False, "long_disabled")
    if side == "SHORT" and (not settings_row.short_enabled or ctx.short_disabled_for_symbol):
        return RiskCheckResult(False, "short_disabled")

    effective_leverage = settings_row.leverage
    max_leverage = ctx.max_leverage_override or settings_row.max_allowed_leverage
    if effective_leverage > max_leverage:
        return RiskCheckResult(False, "leverage_exceeds_max_allowed")

    return RiskCheckResult(True)


def evaluate_portfolio_risk(settings_row: BotSettings, ctx: RiskContext, side: str) -> RiskCheckResult:
    if not settings_row.auto_trading_enabled:
        return RiskCheckResult(False, "auto_trading_disabled")
    return _portfolio_checks(settings_row, ctx, side)


def evaluate_manual_trade_risk(settings_row: BotSettings, ctx: RiskContext, side: str) -> RiskCheckResult:
    return _portfolio_checks(settings_row, ctx, side)


def check_liquidation_distance(
    stop_loss_distance_pct: Decimal, min_liquidation_distance_pct: Decimal
) -> RiskCheckResult:
    if stop_loss_distance_pct < min_liquidation_distance_pct:
        return RiskCheckResult(False, "liquidation_distance_too_small")
    return RiskCheckResult(True)

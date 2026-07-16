"""Musteri (tenant) bazli ortak sorgu yardimcilari."""

from __future__ import annotations

from datetime import date as date_type, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BinanceConnectionStatus, DailyStatistic, SymbolRule
from shared.db.base import new_uuid
from shared.timezone_utils import local_today


async def get_or_create_daily_statistic(
    session: AsyncSession,
    admin_id: str,
    bot_mode: str,
    stat_date: date_type | None = None,
) -> DailyStatistic:
    day = stat_date or local_today()
    result = await session.execute(
        select(DailyStatistic).where(
            DailyStatistic.admin_id == admin_id,
            DailyStatistic.stat_date == day,
            DailyStatistic.bot_mode == bot_mode,
        )
    )
    stat = result.scalar_one_or_none()
    if stat is not None:
        return stat
    stat = DailyStatistic(
        stat_date=day,
        bot_mode=bot_mode,
        admin_id=admin_id,
        trades_count=0,
        winning_trades=0,
        losing_trades=0,
        win_rate_pct=Decimal("0"),
        gross_pnl_usdt=Decimal("0"),
        net_pnl_usdt=Decimal("0"),
        total_commission_usdt=Decimal("0"),
        total_funding_usdt=Decimal("0"),
        consecutive_losses=0,
    )
    session.add(stat)
    await session.flush()
    return stat


async def get_or_create_symbol_rule(session: AsyncSession, admin_id: str, symbol: str) -> SymbolRule:
    result = await session.execute(
        select(SymbolRule).where(SymbolRule.admin_id == admin_id, SymbolRule.symbol == symbol)
    )
    rule = result.scalar_one_or_none()
    if rule is not None:
        return rule
    rule = SymbolRule(
        id=new_uuid(),
        admin_id=admin_id,
        symbol=symbol,
        in_analysis_list=True,
        is_blacklisted=False,
        long_enabled=True,
        short_enabled=True,
    )
    session.add(rule)
    await session.flush()
    return rule


async def get_or_create_connection_status(
    session: AsyncSession,
    admin_id: str,
    environment: str,
) -> BinanceConnectionStatus:
    result = await session.execute(
        select(BinanceConnectionStatus).where(
            BinanceConnectionStatus.admin_id == admin_id,
            BinanceConnectionStatus.id == environment,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = BinanceConnectionStatus(id=environment, admin_id=admin_id)
    session.add(row)
    await session.flush()
    return row
